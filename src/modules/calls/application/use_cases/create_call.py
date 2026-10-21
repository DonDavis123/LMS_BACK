from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.calls.application.dto.create_call import CreateCallDTO
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.calls.domain.entities.call import Call
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole


class CreateCallUseCase:

    def __init__(
        self,
        call_repository: CallRepository,
        user_repository: UserRepository,
        lead_repository: LeadRepository,
        contact_repository: ContactRepository,
        account_repository: AccountRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.call_repository = call_repository
        self.user_repository = user_repository
        self.lead_repository = lead_repository
        self.contact_repository = contact_repository
        self.account_repository = account_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(
        self,
        data: CreateCallDTO,
    ) -> Call:
        if data.created_by_id is None:
            raise ValueError("Call creator is required.")

        # The user who made the call; defaults to whoever logs it.
        owner_id = data.owner_id or data.created_by_id

        owner = self.user_repository.get_by_id(owner_id)

        if owner is None or owner.is_deleted:
            raise ValueError("Call owner does not exist.")

        if not owner.is_active:
            raise ValueError("Call owner is inactive.")

        if owner.role not in {
            UserRole.ADMIN,
            UserRole.SUPERADMIN,
        }:
            raise ValueError(
                "Call owner must be an ADMIN or SUPERADMIN."
            )

        creator = self.user_repository.get_by_id(data.created_by_id)

        if creator is None:
            raise ValueError("Call creator does not exist.")

        if not creator.is_active:
            raise ValueError("Call creator is inactive.")

        if data.lead_id is not None:
            lead = self.lead_repository.get_by_id(data.lead_id)

            if lead is None or lead.is_deleted:
                raise ValueError("Selected lead not found.")

        if data.contact_id is not None:
            contact = self.contact_repository.get_by_id(data.contact_id)

            if contact is None or contact.is_deleted:
                raise ValueError("Selected contact not found.")

        if data.account_id is not None:
            account = self.account_repository.get_by_id(data.account_id)

            if account is None or account.is_deleted:
                raise ValueError("Selected account not found.")

        call = Call.create(
            owner_id=owner_id,
            created_by_id=data.created_by_id,
            call_start_time=data.call_start_time,
            outcome=data.outcome,
            lead_id=data.lead_id,
            contact_id=data.contact_id,
            account_id=data.account_id,
            call_type=data.call_type,
            duration_seconds=data.duration_seconds,
            description=data.description,
            entry_method=data.entry_method,
        )

        def creation():
            saved = self.call_repository.save(call)

            targets = [("CALL", saved.id)]
            if saved.lead_id:
                targets.append(("LEAD", saved.lead_id))
            if saved.contact_id:
                targets.append(("CONTACT", saved.contact_id))
            if saved.account_id:
                targets.append(("ACCOUNT", saved.account_id))

            self.timeline_recorder.record(
                event_type="CALL_LOGGED",
                actor_id=saved.created_by_id,
                message=(
                    f"Call logged ({saved.outcome.value}, "
                    f"{saved.duration_label()})."
                ),
                metadata={
                    "call_id": str(saved.id),
                    "outcome": saved.outcome.value,
                    "duration_seconds": saved.duration_seconds,
                    "description": saved.description,
                },
                targets=targets,
            )
            return saved

        return self.transaction_manager.execute(creation)
