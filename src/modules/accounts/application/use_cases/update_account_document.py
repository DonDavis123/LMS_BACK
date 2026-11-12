from uuid import UUID

from src.modules.accounts.application.dto.account_document import (
    GetAccountDocumentDTO,
    UpdateAccountDocumentDTO,
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


class UpdateAccountDocumentUseCase:

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
        data: UpdateAccountDocumentDTO,
        current_user_id: UUID,
    ) -> GetAccountDocumentDTO:
        account = self.account_repository.get_by_id(data.account_id)

        if account is None or account.is_deleted:
            raise ValueError("Account not found.")

        document = self.document_repository.get_by_id(
            data.document_id,
            account.id,
        )

        if document is None:
            raise ValueError("Document not found.")

        old_name, old_url = document.name, document.url
        document.update(
            name=data.name,
            url=data.url,
            modified_by_id=current_user_id,
        )

        def update() -> GetAccountDocumentDTO:
            saved = self.document_repository.save(document)

            if (old_name, old_url) != (saved.name, saved.url):
                self.timeline_recorder.record(
                    event_type="ACCOUNT_DOCUMENT_UPDATED",
                    actor_id=current_user_id,
                    message=(
                        f'Document "{saved.name}" of account '
                        f"{account.account_name} was updated."
                    ),
                    metadata={
                        "document_id": str(saved.id),
                        "changes": {
                            "name": {"old": old_name, "new": saved.name},
                            "url": {"old": old_url, "new": saved.url},
                        },
                    },
                    targets=[("ACCOUNT", account.id)],
                )

            return self.document_repository.get_with_relations(saved.id)

        return self.transaction_manager.execute(update)
