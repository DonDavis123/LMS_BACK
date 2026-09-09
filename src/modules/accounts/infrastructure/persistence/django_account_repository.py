from uuid import UUID

from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.accounts.domain.entities.account import Account

from .django_account_model import DjangoAccountModel


class DjangoAccountRepository(AccountRepository):

    def save(self, account: Account) -> Account:
        model, created = DjangoAccountModel.objects.update_or_create(
            id=account.id,
            defaults={
                "account_owner_id": account.account_owner_id,
                "account_name": account.account_name,
                "account_site": account.account_site,
                "account_number": account.account_number,
                "account_type": account.account_type,
                "industry": account.industry,
                "annual_revenue": account.annual_revenue,
                "rating": account.rating,
                "phone": account.phone,
                "website": account.website,
                "ticker_symbol": account.ticker_symbol,
                "ownership": account.ownership,
                "employees": account.employees,
                "sic_code": account.sic_code,
                "created_by_id": account.created_by_id,
                "created_at": account.created_at,
                "modified_by_id": account.modified_by_id,
                "updated_at": account.updated_at,
                "is_deleted": account.is_deleted,
            },
        )

        return self._to_domain(model)

    def get_by_id(
        self,
        account_id: UUID,
    ) -> Account | None:

        try:
            model = DjangoAccountModel.objects.get(
                id=account_id,
            )
        except DjangoAccountModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def get_all(self) -> list[Account]:

        models = DjangoAccountModel.objects.filter(
            is_deleted=False,
        )

        return [
            self._to_domain(model)
            for model in models
        ]

    @staticmethod
    def _to_domain(
        model: DjangoAccountModel,
    ) -> Account:

        return Account(
            id=model.id,
            account_owner_id=model.account_owner_id,
            account_name=model.account_name,
            account_site=model.account_site,
            account_number=model.account_number,
            account_type=model.account_type,
            industry=model.industry,
            annual_revenue=model.annual_revenue,
            rating=model.rating,
            phone=model.phone,
            website=model.website,
            ticker_symbol=model.ticker_symbol,
            ownership=model.ownership,
            employees=model.employees,
            sic_code=model.sic_code,
            created_by_id=model.created_by_id,
            created_at=model.created_at,
            modified_by_id=model.modified_by_id,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )