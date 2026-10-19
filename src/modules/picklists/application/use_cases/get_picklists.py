from src.modules.picklists.application.dto.picklist_dto import (
    PicklistFieldDTO,
    PicklistOptionDTO,
)
from src.modules.picklists.application.interfaces.picklist_repository import (
    PicklistRepository,
)
from src.modules.picklists.application.interfaces.picklist_usage_gateway import (
    PicklistUsageGateway,
)
from src.modules.picklists.domain.entities.picklist_catalog import (
    get_module_fields,
    get_picklist_field,
)


class GetPicklistsUseCase:
    def __init__(
        self,
        picklist_repository: PicklistRepository,
        usage_gateway: PicklistUsageGateway,
    ):
        self.picklist_repository = picklist_repository
        self.usage_gateway = usage_gateway

    def execute(
        self,
        module: str,
        field: str | None = None,
        include_inactive: bool = False,
    ) -> list[PicklistFieldDTO]:
        definitions = (
            [get_picklist_field(module, field)]
            if field
            else get_module_fields(module)
        )

        self.picklist_repository.ensure_defaults(module)

        result = []
        for definition in definitions:
            options = self.picklist_repository.list_options(
                module, definition.key, include_inactive=include_inactive
            )
            usage = (
                self.usage_gateway.count_by_value(module, definition.key)
                if include_inactive
                else {}
            )
            result.append(
                PicklistFieldDTO(
                    module=module,
                    field=definition.key,
                    label=definition.label,
                    options=[
                        PicklistOptionDTO(
                            id=option.id,
                            value=option.value,
                            sort_order=option.sort_order,
                            is_active=option.is_active,
                            is_system=option.is_system,
                            usage_count=(
                                usage.get(option.value, 0) if include_inactive else None
                            ),
                        )
                        for option in options
                    ],
                )
            )
        return result
