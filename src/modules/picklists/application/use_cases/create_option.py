from src.modules.picklists.application.interfaces.picklist_repository import (
    PicklistRepository,
)
from src.modules.picklists.domain.entities.picklist_catalog import (
    MAX_OPTIONS_PER_FIELD,
    get_picklist_field,
)
from src.modules.picklists.domain.entities.picklist_option import (
    PicklistOption,
    normalize_option_value,
)


class CreatePicklistOptionUseCase:
    def __init__(self, picklist_repository: PicklistRepository):
        self.picklist_repository = picklist_repository

    def execute(self, module: str, field: str, value: str) -> PicklistOption:
        definition = get_picklist_field(module, field)
        text = normalize_option_value(value, definition)

        self.picklist_repository.ensure_defaults(module)

        if self.picklist_repository.find_by_value(module, field, text) is not None:
            raise ValueError(f'"{text}" already exists for {definition.label}.')

        if self.picklist_repository.count(module, field) >= MAX_OPTIONS_PER_FIELD:
            raise ValueError(
                f"{definition.label} cannot have more than "
                f"{MAX_OPTIONS_PER_FIELD} options."
            )

        option = PicklistOption.create(
            module=module,
            field=field,
            value=text,
            sort_order=self.picklist_repository.next_sort_order(module, field),
        )
        return self.picklist_repository.save(option)
