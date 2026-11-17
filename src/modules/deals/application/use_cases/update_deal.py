from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.deals.application.dto.update_deal import UpdateDealDTO
from src.modules.deals.application.interfaces.deal_repository import DealRepository
from src.modules.deals.application.services.deal_timeline import (
    FIELD_LABELS,
    clip,
    record_stage_events,
    snapshot,
    targets_for,
)
from src.modules.deals.application.services.deal_validation import (
    validate_account_and_contact,
    validate_owner,
)
from src.modules.deals.domain.entities.deal import (
    Deal,
    validate_amount,
    validate_name,
)
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.timeline.application.interfaces.timeline_recorder import (
    TimelineRecorder,
)
from src.modules.timeline.application.services.change_tracker import (
    build_field_changes,
    format_field_changes,
    resolve_relationship_changes,
)
from src.modules.users.application.interfaces.user_repository import UserRepository

UPDATEABLE_FIELDS = frozenset({
    "name",
    "amount",
    "expected_close_date",
    "stage",
    "probability",
    "owner_id",
    "account_id",
    "contact_id",
    "description",
    "lost_reason",
})


class UpdateDealUseCase:

    def __init__(
        self,
        deal_repository: DealRepository,
        user_repository: UserRepository,
        contact_repository: ContactRepository,
        account_repository: AccountRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.deal_repository = deal_repository
        self.user_repository = user_repository
        self.contact_repository = contact_repository
        self.account_repository = account_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, data: UpdateDealDTO, current_user_id=None) -> Deal:
        deal = self.deal_repository.get_by_id(data.deal_id)

        if deal is None:
            raise ValueError("Deal not found.")

        fields = data.fields

        unknown = set(fields) - UPDATEABLE_FIELDS
        if unknown:
            raise ValueError(
                f"Field '{sorted(unknown)[0]}' cannot be updated."
            )

        def update():
            from_stage = deal.stage
            old_values = snapshot(deal)

            if "name" in fields:
                deal.name = validate_name(fields["name"])

            if "amount" in fields:
                deal.amount = validate_amount(fields["amount"])

            if "expected_close_date" in fields:
                deal.expected_close_date = fields["expected_close_date"]

            if "description" in fields:
                deal.description = fields["description"]

            if "owner_id" in fields:
                validate_owner(self.user_repository, fields["owner_id"])
                deal.owner_id = fields["owner_id"]

            if "account_id" in fields or "contact_id" in fields:
                if "account_id" in fields:
                    deal.account_id = fields["account_id"]
                if "contact_id" in fields:
                    deal.contact_id = fields["contact_id"]
                validate_account_and_contact(
                    self.account_repository,
                    self.contact_repository,
                    deal.account_id,
                    deal.contact_id,
                )

            # Stage / probability / lost reason follow the stage rules.
            if "stage" in fields:
                deal.move_to_stage(
                    fields["stage"],
                    probability=fields.get("probability"),
                    lost_reason=fields.get("lost_reason"),
                )
            else:
                if fields.get("probability") is not None:
                    deal.set_probability(fields["probability"])
                elif "probability" in fields:
                    raise ValueError(
                        "Probability must be an integer between 0 and 100."
                    )
                if "lost_reason" in fields:
                    deal.set_lost_reason(fields["lost_reason"])

            saved = self.deal_repository.save(deal)

            changes = build_field_changes(old_values, snapshot(saved))

            changes = resolve_relationship_changes(
                changes,
                {
                    "owner_id": lambda user_id: (
                        user.name
                        if (user := self.user_repository.get_by_id(user_id))
                        else None
                    ),
                    "account_id": lambda account_id: (
                        account.account_name
                        if (
                            account := self.account_repository.get_by_id(
                                account_id
                            )
                        )
                        else None
                    ),
                    "contact_id": lambda contact_id: (
                        contact.name
                        if (
                            contact := self.contact_repository.get_by_id(
                                contact_id
                            )
                        )
                        else None
                    ),
                },
            )

            if changes:
                actor_id = current_user_id or saved.owner_id

                self.timeline_recorder.record(
                    event_type="DEAL_UPDATED",
                    actor_id=actor_id,
                    message=clip(
                        f"Deal {saved.name} was updated. Changes: "
                        f"{format_field_changes(changes, FIELD_LABELS)}"
                    ),
                    metadata={
                        "deal_id": str(saved.id),
                        "name": saved.name,
                        "changes": changes,
                    },
                    targets=targets_for(saved),
                )
                # A stage change made through PATCH is also a stage event.
                record_stage_events(
                    self.timeline_recorder, saved, from_stage, actor_id
                )

            return saved

        return self.transaction_manager.execute(update)
