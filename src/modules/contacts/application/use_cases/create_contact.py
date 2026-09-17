from uuid import UUID

from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.contacts.application.dto.create_contact import (
    CreateContactDTO,
)
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.contacts.domain.entities.contact import Contact
from src.modules.users.application.interfaces.user_repository import (
    UserRepository,
)
from src.modules.users.domain.entities.role import UserRole
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class CreateContactUseCase:

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

    def execute(
        self,
        data: CreateContactDTO,
        current_user_id: UUID,
    ) -> Contact:

        # Validate Account only when an Account is provided
        if data.account_id is not None:
            account = self.account_repository.get_by_id(data.account_id)

            if account is None:
                raise ValueError("Account not found.")

            if account.is_deleted:
                raise ValueError(
                    "Cannot create a Contact for a deleted Account."
                )

        # Resolve Contact owner
        contact_owner_id = data.contact_owner_id or current_user_id

        owner = self.user_repository.get_by_id(contact_owner_id)

        if owner is None:
            raise ValueError("Selected contact owner does not exist.")

        if not owner.is_active:
            raise ValueError("Selected contact owner is inactive.")

        if owner.role not in {
            UserRole.ADMIN,
            UserRole.SUPERADMIN,
        }:
            raise ValueError(
                "Selected contact owner must be an ADMIN or SUPERADMIN."
            )

        # Create Contact
        contact = Contact.create(
            account_id=data.account_id,
            contact_owner_id=contact_owner_id,
            name=data.name,
            email=data.email,
            secondary_email=data.secondary_email,
            phone=data.phone,
            other_phone=data.other_phone,
            mobile=data.mobile,
            home_phone=data.home_phone,
            assistant_phone=data.assistant_phone,
            title=data.title,
            department=data.department,
            lead_source=data.lead_source,
            vendor_name=data.vendor_name,
            date_of_birth=data.date_of_birth,
            assistant=data.assistant,
            email_opt_out=data.email_opt_out,
            reporting_to_id=data.reporting_to_id,
            mailing_address=data.mailing_address,
            mailing_city=data.mailing_city,
            mailing_state=data.mailing_state,
            mailing_country=data.mailing_country,
            mailing_postal_code=data.mailing_postal_code,
            other_address=data.other_address,
            description=data.description,
            created_by_id=current_user_id,
        )

        def creation():
            saved = self.contact_repository.save(contact)
            targets = [("CONTACT", saved.id)] + ([('ACCOUNT', saved.account_id)] if saved.account_id else [])
            self.timeline_recorder.record(event_type="CONTACT_CREATED", actor_id=current_user_id, message=f"Contact {saved.name} was created.", metadata={"contact_id": str(saved.id), "name": saved.name}, targets=targets)
            return saved
        return self.transaction_manager.execute(creation)