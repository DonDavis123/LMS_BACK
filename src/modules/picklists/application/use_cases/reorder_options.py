from uuid import UUID

from src.modules.picklists.application.interfaces.picklist_repository import (
    PicklistRepository,
)
from src.modules.picklists.domain.entities.picklist_catalog import get_picklist_field


class ReorderPicklistOptionsUseCase:
    def __init__(self, picklist_repository: PicklistRepository):
        self.picklist_repository = picklist_repository

    def execute(self, module: str, field: str, ordered_ids: list[UUID]) -> None:
        get_picklist_field(module, field)
        self.picklist_repository.ensure_defaults(module)

        current = self.picklist_repository.list_options(
            module, field, include_inactive=True
        )
        by_id = {option.id: option for option in current}

        if len(set(ordered_ids)) != len(ordered_ids):
            raise ValueError("Each option can only appear once.")
        if set(ordered_ids) != set(by_id):
            raise ValueError(
                "The new order must list every option of this field exactly once."
            )

        ordered = [by_id[option_id] for option_id in ordered_ids]
        for position, option in enumerate(ordered):
            option.sort_order = position
        self.picklist_repository.save_order(ordered)
