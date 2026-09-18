from datetime import datetime, timezone
from uuid import UUID

from src.modules.accounts.application.interfaces.account_repository import AccountRepository
from src.modules.contacts.application.dto.update_contact import UpdateContactDTO
from src.modules.contacts.application.interfaces.contact_repository import ContactRepository
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.timeline.application.services.change_tracker import build_field_changes
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class UpdateContactUseCase:
    def __init__(
        self,
        contact_repository: ContactRepository,
        account_repository: AccountRepository,
        user_repository: UserRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.contact_repository = contact_repository
        self.account_repository = account_repository
        self.user_repository = user_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, data: UpdateContactDTO, current_user_id: UUID):
        contact = self.contact_repository.get_by_id(data.contact_id)
        if contact is None:
            raise ValueError("Contact not found.")

        fields = data.fields
        updateable_fields = (
            "account_id", "contact_owner_id", "name", "email", "secondary_email",
            "phone", "other_phone", "mobile", "home_phone", "assistant_phone", "title",
            "department", "lead_source", "vendor_name", "date_of_birth", "assistant",
            "email_opt_out", "reporting_to_id", "mailing_address", "mailing_city",
            "mailing_state", "mailing_country", "mailing_postal_code", "other_address",
            "description",
        )
        old_values = {field: getattr(contact, field) for field in updateable_fields}

        def update():
            if "account_id" in fields:
                account_id = fields["account_id"]
                if account_id is not None:
                    account = self.account_repository.get_by_id(account_id)
                    if account is None:
                        raise ValueError("Selected Account not found.")
                    if account.is_deleted:
                        raise ValueError("Cannot assign Contact to a deleted Account.")
                contact.account_id = account_id

            if "contact_owner_id" in fields:
                contact_owner_id = fields["contact_owner_id"]
                if contact_owner_id is None:
                    raise ValueError("Contact owner cannot be null.")
                owner = self.user_repository.get_by_id(contact_owner_id)
                if owner is None:
                    raise ValueError("Contact owner does not exist.")
                if not owner.is_active:
                    raise ValueError("Contact owner is inactive.")
                if owner.role not in {UserRole.ADMIN, UserRole.SUPERADMIN}:
                    raise ValueError("Contact owner must be an ADMIN or SUPERADMIN.")
                contact.contact_owner_id = contact_owner_id

            for field in updateable_fields:
                if field in {"account_id", "contact_owner_id"}:
                    continue
                if field in fields:
                    setattr(contact, field, fields[field])

            contact.modified_by_id = current_user_id
            contact.updated_at = datetime.now(timezone.utc)
            saved = self.contact_repository.save(contact)
            new_values = {field: getattr(saved, field) for field in updateable_fields}
            changes = build_field_changes(old_values, new_values)

            if changes:
                targets = [("CONTACT", saved.id)]
                if saved.account_id:
                    targets.append(("ACCOUNT", saved.account_id))
                self.timeline_recorder.record(
                    event_type="CONTACT_UPDATED",
                    actor_id=current_user_id,
                    message=f"Contact {saved.name} was updated.",
                    metadata={"changes": changes},
                    targets=targets,
                )
            return saved

        return self.transaction_manager.execute(update)
