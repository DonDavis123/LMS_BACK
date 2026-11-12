from uuid import UUID

from src.modules.accounts.application.dto.account_document import (
    GetAccountDocumentDTO,
)
from src.modules.accounts.application.interfaces.account_document_repository import (
    AccountDocumentRepository,
)
from src.modules.accounts.domain.entities.account_document import AccountDocument

from .django_account_document_model import DjangoAccountDocumentModel


class DjangoAccountDocumentRepository(AccountDocumentRepository):

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _base_queryset(self):
        return DjangoAccountDocumentModel.objects.filter(
            company_id=self._company_id,
        )

    def save(self, document: AccountDocument) -> AccountDocument:
        model, _ = self._base_queryset().update_or_create(
            id=document.id,
            defaults={
                # Always the repository's own company, never the entity's.
                "company_id": self._company_id,
                "account_id": document.account_id,
                "name": document.name,
                "url": document.url,
                "created_by_id": document.created_by_id,
                "created_at": document.created_at,
                "modified_by_id": document.modified_by_id,
                "updated_at": document.updated_at,
            },
        )

        return self._to_domain(model)

    def get_by_id(
        self,
        document_id: UUID,
        account_id: UUID,
    ) -> AccountDocument | None:
        try:
            model = self._base_queryset().get(
                id=document_id,
                account_id=account_id,
            )
        except DjangoAccountDocumentModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def get_with_relations(
        self,
        document_id: UUID,
    ) -> GetAccountDocumentDTO | None:
        try:
            model = (
                self._base_queryset()
                .select_related("created_by")
                .get(id=document_id)
            )
        except DjangoAccountDocumentModel.DoesNotExist:
            return None

        return self._to_dto(model)

    def list_by_account_id(self, account_id: UUID) -> list[GetAccountDocumentDTO]:
        models = (
            self._base_queryset()
            .filter(account_id=account_id)
            .select_related("created_by")
            .order_by("created_at", "id")
        )

        return [self._to_dto(model) for model in models]

    def delete(self, document_id: UUID) -> None:
        self._base_queryset().filter(id=document_id).delete()

    @staticmethod
    def _to_domain(model: DjangoAccountDocumentModel) -> AccountDocument:
        return AccountDocument(
            id=model.id,
            account_id=model.account_id,
            name=model.name,
            url=model.url,
            created_by_id=model.created_by_id,
            created_at=model.created_at,
            modified_by_id=model.modified_by_id,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_dto(model: DjangoAccountDocumentModel) -> GetAccountDocumentDTO:
        return GetAccountDocumentDTO(
            id=model.id,
            account_id=model.account_id,
            name=model.name,
            url=model.url,
            created_by_id=model.created_by_id,
            created_by_name=model.created_by.name if model.created_by else None,
            created_at=model.created_at,
            modified_by_id=model.modified_by_id,
            updated_at=model.updated_at,
        )
