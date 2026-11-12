from src.modules.accounts.application.dto.create_account_dto import (
    CreateAccountDTO,
)
from src.modules.accounts.application.interfaces.account_document_repository import (
    AccountDocumentRepository,
)
from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.accounts.domain.entities.account import Account
from src.modules.accounts.domain.entities.account_document import AccountDocument
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager
from src.modules.users.application.interfaces.user_repository import UserRepository


class CreateAccountUseCase:

    def __init__(
        self,
        account_repository: AccountRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
        user_repository: UserRepository,
        document_repository: AccountDocumentRepository | None = None,
    ):
        self.account_repository = account_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager
        self.user_repository = user_repository
        self.document_repository = document_repository

    def execute(
        self,
        data: CreateAccountDTO,
        current_user_id,
    ) -> Account:

        account_owner_id = (
            data.account_owner_id
            or current_user_id
        )

        owner = self.user_repository.get_by_id(account_owner_id)
        if owner is None:
            raise ValueError("Account owner not found.")
        # Blocked and retired (soft-deleted) users are inactive.
        if not owner.is_active:
            raise ValueError("Account owner must be an active user.")

        account = Account.create(
            account_owner_id=account_owner_id,
            account_name=data.account_name,
            account_site=data.account_site,
            account_number=data.account_number,
            account_type=data.account_type,
            industry=data.industry,
            annual_revenue=data.annual_revenue,
            rating=data.rating,
            phone=data.phone,
            website=data.website,
            ticker_symbol=data.ticker_symbol,
            ownership=data.ownership,
            employees=data.employees,
            sic_code=data.sic_code,

            # Billing information
            billing_address=data.billing_address,
            billing_city=data.billing_city,
            billing_state=data.billing_state,
            billing_country=data.billing_country,
            billing_postal_code=data.billing_postal_code,

            # Description
            description=data.description,

            created_by_id=current_user_id,
        )

        # Built (and therefore validated) before anything is saved, so a bad
        # document name / URL rejects the whole request and no account is
        # left behind without its documents.
        documents = [
            AccountDocument.create(
                account_id=account.id,
                name=item.name,
                url=item.url,
                created_by_id=current_user_id,
            )
            for item in (data.documents or [])
        ]
        if documents and self.document_repository is None:
            raise ValueError("Documents cannot be saved right now.")

        def creation():
            saved = self.account_repository.save(account)
            self.timeline_recorder.record(event_type="ACCOUNT_CREATED", actor_id=current_user_id, message=f"Account {saved.account_name} was created.", metadata={"account_id": str(saved.id), "account_name": saved.account_name}, targets=[("ACCOUNT", saved.id)])

            for document in documents:
                saved_document = self.document_repository.save(document)
                self.timeline_recorder.record(
                    event_type="ACCOUNT_DOCUMENT_ADDED",
                    actor_id=current_user_id,
                    message=(
                        f'Document "{saved_document.name}" was added to account '
                        f"{saved.account_name}."
                    ),
                    metadata={
                        "document_id": str(saved_document.id),
                        "name": saved_document.name,
                        "url": saved_document.url,
                    },
                    targets=[("ACCOUNT", saved.id)],
                )

            return saved
        return self.transaction_manager.execute(creation)
