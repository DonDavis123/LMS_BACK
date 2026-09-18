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

    return ListQuery(
        filters=filters,
        page=page,
        page_size=page_size,
    )


def _parse_positive_int(value: Any, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid integer.")

    if parsed < 1:
        raise ValueError(f"{field_name} must be greater than or equal to 1.")

    return parsed
