from src.modules.accounts.application.dto.create_account_dto import (
    CreateAccountDTO,
)
from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.accounts.domain.entities.account import Account
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class CreateAccountUseCase:

    def __init__(
        self,
        account_repository: AccountRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.account_repository = account_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(
        self,
        data: CreateAccountDTO,
        current_user_id,
    ) -> Account:

        account_owner_id = (
            data.account_owner_id
            or current_user_id
        )

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

        def creation():
            saved = self.account_repository.save(account)
            self.timeline_recorder.record(event_type="ACCOUNT_CREATED", actor_id=current_user_id, message=f"Account {saved.account_name} was created.", metadata={"account_id": str(saved.id), "account_name": saved.account_name}, targets=[("ACCOUNT", saved.id)])
            return saved
        return self.transaction_manager.execute(creation)
