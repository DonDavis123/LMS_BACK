import json
from typing import Any

from src.modules.shared.application.dto.list_query import (
    FilterCondition,
    ListQuery,
)


def parse_list_query(query_params: Any) -> ListQuery:
    page = _parse_positive_int(query_params.get("page", "1"), "page")
    page_size = _parse_positive_int(
        query_params.get("page_size", "20"),
        "page_size",
    )

    raw_filters = query_params.get("filters")
    filters: tuple[FilterCondition, ...] = ()

    if raw_filters:
        try:
            decoded = json.loads(raw_filters)
        except (TypeError, json.JSONDecodeError):
            raise ValueError("The filters parameter must contain valid JSON.")

        if not isinstance(decoded, list):
            raise ValueError("The filters parameter must be a JSON array.")

        parsed: list[FilterCondition] = []
        for index, item in enumerate(decoded):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Filter at index {index} must be a JSON object."
                )

            field = item.get("field")
            operator = item.get("operator")
            if not isinstance(field, str) or not field.strip():
                raise ValueError(
                    f"Filter at index {index} must contain a valid field."
                )
            if not isinstance(operator, str) or not operator.strip():
                raise ValueError(
                    f"Filter at index {index} must contain a valid operator."
                )
            if "value" not in item:
                raise ValueError(
                    f"Filter at index {index} must contain a value."
                )

            parsed.append(
                FilterCondition(
                    field=field.strip(),
                    operator=operator.strip(),
                    value=item["value"],
                )
            )

        filters = tuple(parsed)

    sort_by = query_params.get("sort_by")
    sort_by = sort_by.strip() if isinstance(sort_by, str) else None
    sort_by = sort_by or None

    sort_direction = query_params.get("sort_direction")
    if isinstance(sort_direction, str) and sort_direction.strip():
        sort_direction = sort_direction.strip().lower()
    else:
        sort_direction = "asc" if sort_by else "desc"
    if sort_direction not in {"asc", "desc"}:
        raise ValueError("The sort_direction parameter must be 'asc' or 'desc'.")

    search = query_params.get("search")
    search = search.strip() if isinstance(search, str) else None
    search = search or None

    return ListQuery(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_direction=sort_direction,
        search=search,
    )


def _parse_positive_int(value: Any, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid integer.")

    if parsed < 1:
        raise ValueError(f"{field_name} must be greater than or equal to 1.")

    return parsed
