from datetime import datetime, timezone
from uuid import UUID

from src.modules.accounts.application.dto.update_account import UpdateAccountDTO
from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder


class UpdateAccountUseCase:
    def __init__(
        self,
        account_repository: AccountRepository,
        timeline_recorder: TimelineRecorder,
    ):
        self.account_repository = account_repository
        self.timeline_recorder = timeline_recorder

    def execute(
        self,
        data: UpdateAccountDTO,
        current_user_id: UUID,
    ):
        account = self.account_repository.get_by_id(
            data.account_id,
        )

        if account is None:
            raise ValueError("Account not found.")

        if account.is_deleted:
            raise ValueError("Deleted Account cannot be updated.")
        old_values = {"account_name": account.account_name, "account_site": account.account_site, "account_number": account.account_number, "account_type": account.account_type, "industry": account.industry, "annual_revenue": account.annual_revenue, "rating": account.rating, "phone": account.phone, "website": account.website, "ticker_symbol": account.ticker_symbol, "ownership": account.ownership, "employees": account.employees, "sic_code": account.sic_code, "description": account.description}
        account.account_name = data.account_name
        account.account_site = data.account_site
        account.account_number = data.account_number
        account.account_type = data.account_type
        account.industry = data.industry
        account.annual_revenue = data.annual_revenue
        account.rating = data.rating
        account.phone = data.phone
        account.website = data.website
        account.ticker_symbol = data.ticker_symbol

        if data.ownership is not None:
            account.ownership = data.ownership

        account.employees = data.employees
        account.sic_code = data.sic_code

        account.billing_address = data.billing_address
        account.billing_city = data.billing_city
        account.billing_state = data.billing_state
        account.billing_country = data.billing_country
        account.billing_postal_code = data.billing_postal_code

        account.description = data.description

        # Backend-controlled audit fields
        account.modified_by_id = current_user_id
        account.updated_at = datetime.now(timezone.utc)

        saved = self.account_repository.save(account)
        changes = {f: {"old": old, "new": getattr(saved, f)} for f, old in old_values.items() if old != getattr(saved, f)}
        if changes:
            self.timeline_recorder.record(event_type="ACCOUNT_UPDATED", actor_id=current_user_id, message=f"Account {saved.account_name} was updated.", metadata={"changes": changes}, targets=[("ACCOUNT", saved.id)])
        return saved
