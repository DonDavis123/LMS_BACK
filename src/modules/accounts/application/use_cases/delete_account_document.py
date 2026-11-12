from uuid import UUID

from src.modules.accounts.application.dto.account_document import (
    DeleteAccountDocumentDTO,
)
from src.modules.accounts.application.interfaces.account_document_repository import (
    AccountDocumentRepository,
)
from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.timeline.application.interfaces.timeline_recorder import (
    TimelineRecorder,
)


class DeleteAccountDocumentUseCase:

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
        data: DeleteAccountDocumentDTO,
        current_user_id: UUID,
    ) -> None:
        account = self.account_repository.get_by_id(data.account_id)

        if account is None or account.is_deleted:
            raise ValueError("Account not found.")

        document = self.document_repository.get_by_id(
            data.document_id,
            account.id,
        )

        if document is None:
            raise ValueError("Document not found.")

        def deletion() -> None:
            self.document_repository.delete(document.id)

            self.timeline_recorder.record(
                event_type="ACCOUNT_DOCUMENT_DELETED",
                actor_id=current_user_id,
                message=(
                    f'Document "{document.name}" was removed from account '
                    f"{account.account_name}."
                ),
                metadata={
                    "document_id": str(document.id),
                    "name": document.name,
                    "url": document.url,
                },
                targets=[("ACCOUNT", account.id)],
            )

        self.transaction_manager.execute(deletion)
