from datetime import datetime, timezone
from uuid import UUID

from src.modules.accounts.application.dto.update_account import UpdateAccountDTO
from src.modules.accounts.application.interfaces.account_repository import AccountRepository
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.timeline.application.services.change_tracker import (
    build_field_changes,
    format_field_changes,
)
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class UpdateAccountUseCase:
    def __init__(
        self,
        account_repository: AccountRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.account_repository = account_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, data: UpdateAccountDTO, current_user_id: UUID):
        account = self.account_repository.get_by_id(data.account_id)
        if account is None:
            raise ValueError("Account not found.")
        if account.is_deleted:
            raise ValueError("Deleted Account cannot be updated.")

        updateable_fields = (
            "account_name", "account_site", "account_number", "account_type", "industry",
            "annual_revenue", "rating", "phone", "website", "ticker_symbol", "ownership",
            "employees", "sic_code", "billing_address", "billing_city", "billing_state",
            "billing_country", "billing_postal_code", "description",
        )
        old_values = {field: getattr(account, field) for field in updateable_fields}

        def update():
            for field in updateable_fields:
                setattr(account, field, getattr(data, field))

            account.modified_by_id = current_user_id
            account.updated_at = datetime.now(timezone.utc)
            saved = self.account_repository.save(account)
            new_values = {field: getattr(saved, field) for field in updateable_fields}
            changes = build_field_changes(old_values, new_values)

            if changes:
                change_summary = format_field_changes(
                    changes,
                    field_labels={
                        "account_name": "Account Name",
                        "account_site": "Account Site",
                        "account_number": "Account Number",
                        "account_type": "Account Type",
                        "industry": "Industry",
                        "annual_revenue": "Annual Revenue",
                        "rating": "Rating",
                        "phone": "Phone",
                        "website": "Website",
                        "ticker_symbol": "Ticker Symbol",
                        "ownership": "Ownership",
                        "employees": "Employees",
                        "sic_code": "SIC Code",
                        "billing_address": "Billing Address",
                        "billing_city": "Billing City",
                        "billing_state": "Billing State",
                        "billing_country": "Billing Country",
                        "billing_postal_code": "Billing Postal Code",
                        "description": "Description",
                    },
                )
                self.timeline_recorder.record(
                    event_type="ACCOUNT_UPDATED",
                    actor_id=current_user_id,
                    message=(
                        f"Account {saved.account_name} was updated. "
                        f"Changes: {change_summary}"
                    ),
                    metadata={"changes": changes},
                    targets=[("ACCOUNT", saved.id)],
                )
            return saved

        return self.transaction_manager.execute(update)
