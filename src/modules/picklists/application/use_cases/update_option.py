from uuid import UUID

from src.modules.picklists.application.interfaces.picklist_repository import (
    PicklistRepository,
)
from src.modules.picklists.application.interfaces.picklist_usage_gateway import (
    PicklistUsageGateway,
)
from src.modules.picklists.domain.entities.picklist_catalog import get_picklist_field
from src.modules.picklists.domain.entities.picklist_option import (
    PicklistOption,
    normalize_option_value,
)
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)

_UNSET = object()


class UpdatePicklistOptionUseCase:
    """Rename an option and/or show or hide it."""

    def __init__(
        self,
        picklist_repository: PicklistRepository,
        usage_gateway: PicklistUsageGateway,
        transaction_manager: TransactionManager,
    ):
        self.picklist_repository = picklist_repository
        self.usage_gateway = usage_gateway
        self.transaction_manager = transaction_manager

    def execute(
        self,
        option_id: UUID,
        value: str | object = _UNSET,
        is_active: bool | object = _UNSET,
    ) -> PicklistOption:
        option = self.picklist_repository.get_by_id(option_id)
        if option is None:
            raise ValueError("Option not found.")

        definition = get_picklist_field(option.module, option.field)
        old_value = option.value

        if value is not _UNSET:
            new_value = normalize_option_value(value, definition)
            if new_value != old_value:
                clash = self.picklist_repository.find_by_value(
                    option.module, option.field, new_value
                )
                if clash is not None and clash.id != option.id:
                    raise ValueError(
                        f'"{new_value}" already exists for {definition.label}.'
                    )
                option.rename(new_value)

        if is_active is not _UNSET:
            if is_active:
                option.activate()
            else:
                option.deactivate()

        def apply() -> PicklistOption:
            saved = self.picklist_repository.save(option)
            if saved.value != old_value:
                # Records store the option's text, so a rename must follow
                # them or they would be left pointing at a value that no
                # longer exists.
                self.usage_gateway.replace_value(
                    option.module, option.field, old_value, saved.value
                )
            return saved

        return self.transaction_manager.execute(apply)
