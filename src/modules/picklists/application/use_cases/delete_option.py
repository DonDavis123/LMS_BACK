from uuid import UUID

from src.modules.picklists.application.interfaces.picklist_repository import (
    PicklistRepository,
)
from src.modules.picklists.application.interfaces.picklist_usage_gateway import (
    PicklistUsageGateway,
)
from src.modules.picklists.domain.entities.picklist_catalog import SYSTEM_VALUE
from src.modules.picklists.domain.exceptions import PicklistOptionInUseError
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)


class DeletePicklistOptionUseCase:
    """Delete an option.

    An option that records still use is never dropped silently: the caller
    must either pick a replacement (``replace_with``) that those records are
    moved to, or hide the option instead of deleting it.
    """

    def __init__(
        self,
        picklist_repository: PicklistRepository,
        usage_gateway: PicklistUsageGateway,
        transaction_manager: TransactionManager,
    ):
        self.picklist_repository = picklist_repository
        self.usage_gateway = usage_gateway
        self.transaction_manager = transaction_manager

    def execute(self, option_id: UUID, replace_with: UUID | None = None) -> int:
        """Returns how many records were moved to the replacement."""
        option = self.picklist_repository.get_by_id(option_id)
        if option is None:
            raise ValueError("Option not found.")

        option.ensure_deletable()

        usage = self.usage_gateway.count(option.module, option.field, option.value)

        replacement = None
        if replace_with is not None:
            replacement = self.picklist_repository.get_by_id(replace_with)
            if (
                replacement is None
                or replacement.module != option.module
                or replacement.field != option.field
            ):
                raise ValueError("Replacement option not found.")
            if replacement.id == option.id:
                raise ValueError("Choose a different option as the replacement.")
            if not replacement.is_active:
                raise ValueError("The replacement option must be active.")

        if usage > 0 and replacement is None:
            raise PicklistOptionInUseError(
                f'"{option.value}" is used by {usage} record(s). '
                "Choose a replacement option, or hide it instead of deleting it.",
                usage_count=usage,
            )

        def apply() -> int:
            # Visible records move to the chosen replacement. Records nobody
            # sees any more (deleted / converted) are moved too, or parked on
            # the built-in "None" when no replacement was given, so none is
            # left pointing at an option that no longer exists.
            target = replacement.value if replacement is not None else SYSTEM_VALUE
            changed = self.usage_gateway.replace_value(
                option.module, option.field, option.value, target
            )
            self.picklist_repository.delete(option.id)
            return changed if replacement is not None else 0

        return self.transaction_manager.execute(apply)
