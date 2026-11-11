from __future__ import annotations

from dataclasses import replace
from typing import Any, Sequence

from src.modules.mailing.application.dto.resolve_recipients import FilterSpec
from src.modules.mailing.application.interfaces.record_readers import (
    ListUseCasePort,
)
from src.modules.mailing.application.interfaces.recipient_source import (
    SelectionTooLargeError,
)
from src.modules.shared.application.dto.list_query import FilterCondition, ListQuery

# The list use cases refuse a page larger than ListQuery.MAX_PAGE_SIZE.
PAGE_SIZE = ListQuery.MAX_PAGE_SIZE


def read_all_matching(
    list_use_case: ListUseCasePort,
    search: str | None,
    filters: Sequence[FilterSpec],
    max_matches: int,
) -> list[Any]:
    """Every row a list use case returns for this search and these filters.

    Same approach as the exports module: the module's own list use case is
    asked page by page, so search, filter validation, soft-delete rules and
    tenant scoping are exactly those of the list. The first page is read
    before anything else, so a bad filter or a too large result fails early.
    """
    first_query = ListQuery(
        filters=tuple(
            FilterCondition(field=f.field, operator=f.operator, value=f.value)
            for f in filters
        ),
        page=1,
        page_size=PAGE_SIZE,
        search=search,
    )
    first_page = list_use_case.execute(first_query)

    if first_page.total > max_matches:
        raise SelectionTooLargeError(
            f"This selection matches {first_page.total} records, more than the "
            f"limit of {max_matches}. Narrow the search or filters and try again."
        )

    rows = list(first_page.results)
    for page_number in range(2, first_page.total_pages + 1):
        page = list_use_case.execute(replace(first_query, page=page_number))
        if not page.results:
            break
        rows.extend(page.results)
    return rows
