from uuid import UUID

from django.db.models import Max
from django.db.models.functions import Lower

from src.modules.picklists.application.interfaces.picklist_repository import (
    PicklistRepository,
)
from src.modules.picklists.domain.entities.picklist_catalog import (
    SYSTEM_VALUE,
    get_module_fields,
)
from src.modules.picklists.domain.entities.picklist_option import PicklistOption
from src.modules.picklists.infrastructure.persistence.django_picklist_option_model import (
    DjangoPicklistOptionModel,
)


class DjangoPicklistRepository(PicklistRepository):
    def __init__(self, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _queryset(self):
        # Every query is pinned to this company: that is the tenant boundary.
        return DjangoPicklistOptionModel.objects.filter(company_id=self._company_id)

    # ------------------------------------------------------------------ seed

    def ensure_defaults(self, module: str) -> None:
        for definition in get_module_fields(module):
            exists = self._queryset().filter(
                module=module, field=definition.key
            ).exists()
            if exists:
                continue

            DjangoPicklistOptionModel.objects.bulk_create(
                [
                    DjangoPicklistOptionModel(
                        company_id=self._company_id,
                        module=module,
                        field=definition.key,
                        value=value,
                        sort_order=position,
                        is_active=True,
                        is_system=(value == SYSTEM_VALUE),
                    )
                    for position, value in enumerate(definition.default_values)
                ],
                # Two requests seeding at the same moment must not fail on
                # the unique constraint; the second one just does nothing.
                ignore_conflicts=True,
            )

    # ----------------------------------------------------------------- reads

    def list_options(
        self, module: str, field: str, include_inactive: bool = False
    ) -> list[PicklistOption]:
        queryset = self._queryset().filter(module=module, field=field)
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        return [self._to_domain(model) for model in queryset.order_by("sort_order", "value")]

    def get_by_id(self, option_id: UUID) -> PicklistOption | None:
        model = self._queryset().filter(id=option_id).first()
        return self._to_domain(model) if model else None

    def find_by_value(
        self, module: str, field: str, value: str
    ) -> PicklistOption | None:
        model = (
            self._queryset()
            .annotate(value_lower=Lower("value"))
            .filter(module=module, field=field, value_lower=value.lower())
            .first()
        )
        return self._to_domain(model) if model else None

    def count(self, module: str, field: str) -> int:
        return self._queryset().filter(module=module, field=field).count()

    def next_sort_order(self, module: str, field: str) -> int:
        highest = self._queryset().filter(module=module, field=field).aggregate(
            highest=Max("sort_order")
        )["highest"]
        return 0 if highest is None else highest + 1

    # ---------------------------------------------------------------- writes

    def save(self, option: PicklistOption) -> PicklistOption:
        model, _ = DjangoPicklistOptionModel.objects.update_or_create(
            id=option.id,
            company_id=self._company_id,
            defaults={
                "module": option.module,
                "field": option.field,
                "value": option.value,
                "sort_order": option.sort_order,
                "is_active": option.is_active,
                "is_system": option.is_system,
            },
        )
        return self._to_domain(model)

    def save_order(self, options: list[PicklistOption]) -> None:
        models_by_id = {
            model.id: model
            for model in self._queryset().filter(id__in=[o.id for o in options])
        }
        changed = []
        for option in options:
            model = models_by_id.get(option.id)
            if model is not None and model.sort_order != option.sort_order:
                model.sort_order = option.sort_order
                changed.append(model)
        if changed:
            DjangoPicklistOptionModel.objects.bulk_update(changed, ["sort_order"])

    def delete(self, option_id: UUID) -> None:
        self._queryset().filter(id=option_id).delete()

    # --------------------------------------------------------------- mapping

    @staticmethod
    def _to_domain(model: DjangoPicklistOptionModel) -> PicklistOption:
        return PicklistOption(
            id=model.id,
            module=model.module,
            field=model.field,
            value=model.value,
            sort_order=model.sort_order,
            is_active=model.is_active,
            is_system=model.is_system,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
