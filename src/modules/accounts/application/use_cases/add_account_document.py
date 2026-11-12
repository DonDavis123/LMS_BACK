from uuid import UUID

from src.modules.accounts.application.dto.account_document import (
    AddAccountDocumentDTO,
    GetAccountDocumentDTO,
)
from src.modules.accounts.application.interfaces.account_document_repository import (
    AccountDocumentRepository,
)
from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.accounts.domain.entities.account_document import AccountDocument
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.timeline.application.interfaces.timeline_recorder import (
    TimelineRecorder,
)


class AddAccountDocumentUseCase:

    def __init__(
        self,
        account_repository: AccountRepository,
        document_repository: AccountDocumentRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.account_repository = account_repository
        self.document_repository = document_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(
        self,
        data: AddAccountDocumentDTO,
        current_user_id: UUID,
    ) -> GetAccountDocumentDTO:
        account = self.account_repository.get_by_id(data.account_id)

        if account is None or account.is_deleted:
            raise ValueError("Account not found.")

        document = AccountDocument.create(
            account_id=account.id,
            name=data.name,
            url=data.url,
            created_by_id=current_user_id,
        )

        def creation() -> GetAccountDocumentDTO:
            saved = self.document_repository.save(document)

            self.timeline_recorder.record(
                event_type="ACCOUNT_DOCUMENT_ADDED",
                actor_id=current_user_id,
                message=(
                    f'Document "{saved.name}" was added to account '
                    f"{account.account_name}."
                ),
                metadata={
                    "document_id": str(saved.id),
                    "name": saved.name,
                    "url": saved.url,
                },
                targets=[("ACCOUNT", account.id)],
            )

            return self.document_repository.get_with_relations(saved.id)

        return self.transaction_manager.execute(creation)
