"""All the choices a user makes for one import, in one saved structure.

``ImportOptions.from_dict`` is tolerant (never raises, unknown keys are
ignored) and keeps odd values as they are, so ``validate_options`` can explain
them to the user instead of silently replacing them.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field

from .lead_import_owners import OwnerPlan
from .lead_import_validation import PICKLIST_FIELDS

DUPLICATE_ACTIONS = ("skip", "update", "create_anyway")
MATCH_CHOICES = ("use_existing", "create_new")
OPERATORS = (
    "is_blank", "is_not_blank", "equals", "not_equals", "contains", "not_contains",
)
_VALUE_OPERATORS = ("equals", "not_equals", "contains", "not_contains")

BLANK_VALUE = "__blank__"

MAX_ROW_NUMBERS = 10_000
MAX_RULES = 20
MAX_EXTRA_COLUMNS = 50
MAX_VALUE_MAPPINGS = 500


def _bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "yes", "1"}:
            return True
        if text in {"false", "no", "0"}:
            return False
    return default


def _choice(value, default: str) -> str:
    """A lower-case, trimmed choice; odd values are kept so they get reported."""
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return default


def _text(value) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    return str(value)


def _default_exclusions() -> dict:
    return {"row_numbers": [], "rules": [], "skip_rows_with_errors": False}


def _parse_exclusions(data) -> dict:
    result = _default_exclusions()
    if not isinstance(data, dict):
        return result

    numbers: list[int] = []
    raw_numbers = data.get("row_numbers")
    if isinstance(raw_numbers, (list, tuple)):
        for item in raw_numbers:
            if isinstance(item, bool):
                continue
            try:
                number = int(item)
            except (TypeError, ValueError):
                continue
            if number > 0 and number not in numbers:
                numbers.append(number)
    result["row_numbers"] = numbers

    rules = []
    raw_rules = data.get("rules")
    if isinstance(raw_rules, (list, tuple)):
        for item in raw_rules:
            if not isinstance(item, dict):
                continue
            rules.append(
                {
                    "column": _text(item.get("column")) or "",
                    "operator": _choice(item.get("operator"), ""),
                    "value": _text(item.get("value")),
                }
            )
    result["rules"] = rules
    result["skip_rows_with_errors"] = _bool(data.get("skip_rows_with_errors"), False)
    return result


def _parse_extra_columns(data) -> list[dict]:
    columns = []
    if isinstance(data, (list, tuple)):
        for item in data:
            if isinstance(item, str):
                item = {"column": item}
            if not isinstance(item, dict):
                continue
            column = (_text(item.get("column")) or "").strip()
            if not column:
                continue
            label = (_text(item.get("label")) or "").strip() or column
            columns.append({"column": column, "label": label})
    return columns


def _parse_value_mapping(data) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    if isinstance(data, dict):
        for field_key, values in data.items():
            if not isinstance(field_key, str) or not isinstance(values, dict):
                continue
            entries = {
                raw: target
                for raw, target in values.items()
                if isinstance(raw, str) and isinstance(target, str)
            }
            mapping[field_key] = entries
    return mapping


@dataclass
class ImportOptions:
    duplicate_action: str = "skip"
    owner_plan: dict = dataclass_field(default_factory=lambda: OwnerPlan().to_dict())
    split_multiple_phones: bool = True
    extra_columns: list[dict] = dataclass_field(default_factory=list)  # [{column, label}]
    use_company_as_name: bool = False
    # {field key: {raw file value: option name | "__blank__"}}
    value_mapping: dict[str, dict[str, str]] = dataclass_field(default_factory=dict)
    unknown_values_as_blank: bool = False
    exclusions: dict = dataclass_field(default_factory=_default_exclusions)
    account_match: str = "use_existing"
    contact_match: str = "use_existing"
    allow_repeat: bool = False

    @classmethod
    def from_dict(cls, data) -> "ImportOptions":
        if not isinstance(data, dict):
            return cls()
        return cls(
            duplicate_action=_choice(data.get("duplicate_action"), "skip"),
            owner_plan=OwnerPlan.from_dict(data.get("owner_plan")).to_dict(),
            split_multiple_phones=_bool(data.get("split_multiple_phones"), True),
            extra_columns=_parse_extra_columns(data.get("extra_columns")),
            use_company_as_name=_bool(data.get("use_company_as_name"), False),
            value_mapping=_parse_value_mapping(data.get("value_mapping")),
            unknown_values_as_blank=_bool(data.get("unknown_values_as_blank"), False),
            exclusions=_parse_exclusions(data.get("exclusions")),
            account_match=_choice(data.get("account_match"), "use_existing"),
            contact_match=_choice(data.get("contact_match"), "use_existing"),
            allow_repeat=_bool(data.get("allow_repeat"), False),
        )

    def to_dict(self) -> dict:
        return {
            "duplicate_action": self.duplicate_action,
            "owner_plan": dict(self.owner_plan),
            "split_multiple_phones": self.split_multiple_phones,
            "extra_columns": [dict(c) for c in self.extra_columns],
            "use_company_as_name": self.use_company_as_name,
            "value_mapping": {k: dict(v) for k, v in self.value_mapping.items()},
            "unknown_values_as_blank": self.unknown_values_as_blank,
            "exclusions": {
                "row_numbers": list(self.exclusions.get("row_numbers", [])),
                "rules": [dict(r) for r in self.exclusions.get("rules", [])],
                "skip_rows_with_errors": bool(self.exclusions.get("skip_rows_with_errors")),
            },
            "account_match": self.account_match,
            "contact_match": self.contact_match,
            "allow_repeat": self.allow_repeat,
        }


def validate_options(options: ImportOptions, headers: list[str]) -> list[str]:
    """Plain-English problems with the options (empty list = fine)."""
    errors: list[str] = []
    known_headers = set(headers)

    if options.duplicate_action not in DUPLICATE_ACTIONS:
        errors.append(
            f"The duplicate action '{options.duplicate_action}' is not valid. "
            "Choose Skip, Update existing or Create anyway."
        )
    for label, value in (
        ("account", options.account_match),
        ("contact", options.contact_match),
    ):
        if value not in MATCH_CHOICES:
            errors.append(
                f"The {label} matching choice '{value}' is not valid. "
                "Choose 'use existing' or 'create new'."
            )

    exclusions = options.exclusions
    if len(exclusions.get("row_numbers", [])) > MAX_ROW_NUMBERS:
        errors.append(
            f"You excluded more than {MAX_ROW_NUMBERS:,} rows by number. "
            "Use an exclusion rule instead, or remove those rows from the file."
        )
    rules = exclusions.get("rules", [])
    if len(rules) > MAX_RULES:
        errors.append(
            f"You added {len(rules)} exclusion rules; the limit is {MAX_RULES}. "
            "Remove some rules or combine them."
        )
    for number, rule in enumerate(rules[:MAX_RULES], start=1):
        operator = rule.get("operator")
        column = rule.get("column")
        if operator not in OPERATORS:
            errors.append(
                f"Exclusion rule {number} uses the condition '{operator}', which is not "
                f"supported. Use one of: {', '.join(OPERATORS)}."
            )
        if column not in known_headers:
            errors.append(
                f"Exclusion rule {number} uses the column '{column}', which is not in "
                "your file. Pick one of the columns from your file."
            )
        if operator in _VALUE_OPERATORS and not (rule.get("value") or "").strip():
            errors.append(
                f"Exclusion rule {number} ('{operator}' on '{column}') needs a value to "
                "compare with. Type the value, or use 'is blank' / 'is not blank'."
            )

    if len(options.extra_columns) > MAX_EXTRA_COLUMNS:
        errors.append(
            f"You chose {len(options.extra_columns)} extra columns to add to the "
            f"description; the limit is {MAX_EXTRA_COLUMNS}. Remove some of them."
        )

    total_mappings = sum(len(v) for v in options.value_mapping.values())
    if total_mappings > MAX_VALUE_MAPPINGS:
        errors.append(
            f"You mapped {total_mappings} dropdown values; the limit is "
            f"{MAX_VALUE_MAPPINGS}. Map the most common ones and let the rest "
            "become blank."
        )
    for field_key in options.value_mapping:
        if field_key not in PICKLIST_FIELDS:
            errors.append(
                f"Values can only be mapped for dropdown fields, but '{field_key}' is "
                f"not one. Use one of: {', '.join(PICKLIST_FIELDS)}."
            )

    return errors
