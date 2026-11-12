from datetime import datetime, timezone
from uuid import UUID

from src.modules.accounts.application.dto.update_account import UpdateAccountDTO
from src.modules.accounts.application.interfaces.account_repository import AccountRepository
from src.modules.picklists.application.interfaces.picklist_repository import PicklistRepository
from src.modules.picklists.application.services.option_validation import resolve_option_value
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.timeline.application.services.change_tracker import (
    build_field_changes,
    format_field_changes,
    resolve_relationship_changes,
)
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class UpdateAccountUseCase:
    OPTION_FIELDS = ("industry", "rating", "ownership")

    def __init__(
        self,
        account_repository: AccountRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
        picklist_repository: PicklistRepository | None = None,
        user_repository: UserRepository | None = None,
    ):
        self.account_repository = account_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager
        # The company's own dropdown options. When given, Industry /
        # Rating / Ownership must be one of them. Account Type stays free text.
        self.picklist_repository = picklist_repository
        # Used to check a new Account Owner (a user of the same company).
        self.user_repository = user_repository

    def _option(self, field: str, value, current_value):
        if self.picklist_repository is None:
            return value
        # Keeping the record's current value is always allowed, even if an
        # admin has hidden that option since.
        return resolve_option_value(
            self.picklist_repository, "accounts", field, value, current_value=current_value
        )

    def _check_new_owner(self, owner_id: UUID) -> None:
        if self.user_repository is None:
            raise ValueError("Account owner cannot be changed right now.")
        owner = self.user_repository.get_by_id(owner_id)
        if owner is None:
            raise ValueError("Account owner not found.")
        # Blocked and retired (soft-deleted) users are inactive.
        if not owner.is_active:
            raise ValueError("Account owner must be an active user.")

    def _owner_names(self, changes: dict) -> dict:
        """Show the owner change by name in the Timeline, not by id."""
        if self.user_repository is None or "account_owner_id" not in changes:
            return changes

        def name_of(user_id: UUID) -> str | None:
            user = self.user_repository.get_by_id(user_id)
            return user.name if user else None

        return resolve_relationship_changes(
            changes, {"account_owner_id": name_of},
        )

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
        old_values["account_owner_id"] = account.account_owner_id

        # None means "leave the owner as it is".
        new_owner_id = data.account_owner_id or account.account_owner_id
        if new_owner_id != account.account_owner_id:
            self._check_new_owner(new_owner_id)

        # Checked up front so a bad dropdown value fails before anything changes.
        chosen = {
            field: self._option(field, getattr(data, field), getattr(account, field))
            for field in self.OPTION_FIELDS
        }

        def update():
            for field in updateable_fields:
                if field in chosen:
                    setattr(account, field, chosen[field])
                else:
                    setattr(account, field, getattr(data, field))

            account.account_owner_id = new_owner_id
            account.modified_by_id = current_user_id
            account.updated_at = datetime.now(timezone.utc)
            saved = self.account_repository.save(account)
            new_values = {field: getattr(saved, field) for field in updateable_fields}
            new_values["account_owner_id"] = saved.account_owner_id
            changes = build_field_changes(old_values, new_values)
            changes = self._owner_names(changes)

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
                        "account_owner_id": "Account Owner",
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
