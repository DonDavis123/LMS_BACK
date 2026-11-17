from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.deals.application.dto.create_deal import CreateDealDTO
from src.modules.deals.application.interfaces.deal_repository import DealRepository
from src.modules.deals.application.services.deal_timeline import (
    clip,
    record_stage_events,
    targets_for,
)
from src.modules.deals.application.services.deal_validation import (
    validate_account_and_contact,
    validate_owner,
)
from src.modules.deals.domain.entities.deal import Deal
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.timeline.application.interfaces.timeline_recorder import (
    TimelineRecorder,
)
from src.modules.users.application.interfaces.user_repository import UserRepository


class CreateDealUseCase:

    def __init__(
        self,
        deal_repository: DealRepository,
        user_repository: UserRepository,
        lead_repository: LeadRepository,
        contact_repository: ContactRepository,
        account_repository: AccountRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.deal_repository = deal_repository
        self.user_repository = user_repository
        self.lead_repository = lead_repository
        self.contact_repository = contact_repository
        self.account_repository = account_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, data: CreateDealDTO) -> Deal:
        if data.created_by_id is None:
            raise ValueError("Deal creator is required.")

        validate_owner(self.user_repository, data.owner_id)

        creator = self.user_repository.get_by_id(data.created_by_id)

        if creator is None:
            raise ValueError("Deal creator does not exist.")

        if not creator.is_active:
            raise ValueError("Deal creator is inactive.")

        validate_account_and_contact(
            self.account_repository,
            self.contact_repository,
            data.account_id,
            data.contact_id,
        )

        lead_source = data.lead_source

        if data.source_lead_id is not None:
            lead = self.lead_repository.get_by_id(data.source_lead_id)

            if lead is None or lead.is_deleted:
                raise ValueError("Selected lead not found.")

            # The deal inherits the lead's source unless one was given.
            if lead_source is None:
                lead_source = lead.lead_source

        # Deal.create validates name, amount, stage, probability and
        # lost_reason (all ValueError).
        deal = Deal.create(
            name=data.name,
            owner_id=data.owner_id,
            created_by_id=data.created_by_id,
            amount=data.amount,
            expected_close_date=data.expected_close_date,
            stage=data.stage,
            probability=data.probability,
            account_id=data.account_id,
            contact_id=data.contact_id,
            source_lead_id=data.source_lead_id,
            lead_source=lead_source,
            description=data.description,
            lost_reason=data.lost_reason,
        )

        def creation():
            saved = self.deal_repository.save(deal)

            self.timeline_recorder.record(
                event_type="DEAL_CREATED",
                actor_id=saved.created_by_id,
                message=clip(f"Deal {saved.name} was created."),
                metadata={
                    "deal_id": str(saved.id),
                    "name": saved.name,
                    "stage": saved.stage.value,
                },
                targets=targets_for(saved),
            )
            # Created directly as Won / Lost: record the closing event too.
            record_stage_events(
                self.timeline_recorder, saved, None, saved.created_by_id
            )
            return saved

        return self.transaction_manager.execute(creation)
