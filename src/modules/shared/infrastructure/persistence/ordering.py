from dataclasses import dataclass

from django.db.models import F
from django.db.models.functions import Lower

from src.modules.shared.application.dto.list_query import ListQuery


@dataclass(frozen=True)
class SortableField:
    """
    A list column that can be sorted.

    ``db_field`` is an ORM path or queryset annotation. Text columns are
    compared case-insensitively so the order reads alphabetically
    ("apple" does not sort after "Zebra").
    """

    db_field: str
    is_text: bool = False


def apply_ordering(
    queryset,
    query: ListQuery,
    sortable_fields: dict[str, SortableField],
    default_ordering: tuple[str, ...] = ("-created_at", "-id"),
):
    """
    Orders a list queryset.

    Without ``query.sort_by`` the ``default_ordering`` applies (newest
    first). With it, the requested column is ordered first (empty values
    last) and ``default_ordering`` breaks ties, so pagination stays stable.
    """
    if not query.sort_by:
        return queryset.order_by(*default_ordering)

    config = sortable_fields.get(query.sort_by)
    if config is None:
        raise ValueError(f"Sorting is not supported for field '{query.sort_by}'.")

    expression = Lower(config.db_field) if config.is_text else F(config.db_field)
    ordered = (
        expression.asc(nulls_last=True)
        if query.sort_direction == "asc"
        else expression.desc(nulls_last=True)
    )
    return queryset.order_by(ordered, *default_ordering)
