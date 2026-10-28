"""Column-mapping rules for lead import.

Mapping format: ``{file header: field key | "__ignore__"}``. Headers of the
file that are missing from the mapping are treated as ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field

from .lead_import_fields import IMPORT_FIELDS, IMPORT_FIELDS_BY_KEY
from .lead_import_options import ImportOptions

IGNORE = "__ignore__"

_PHONE_KEYS = ("phone", "mobile_number")
_KNOWN_KEYS = ", ".join(f.key for f in IMPORT_FIELDS)


@dataclass
class MappingCheck:
    errors: list[str] = dataclass_field(default_factory=list)  # block the import
    warnings: list[str] = dataclass_field(default_factory=list)  # allowed

    @property
    def ok(self) -> bool:
        return not self.errors


def _is_ignored(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() in ("", IGNORE))


def mapping_to_columns(mapping: dict) -> dict[str, str]:
    """``{field key: file header}`` for every mapped column (ignored ones are
    skipped). This is what ``validate_row`` needs for its messages."""
    columns: dict[str, str] = {}
    for header, field_key in (mapping or {}).items():
        if _is_ignored(field_key) or not isinstance(field_key, str):
            continue
        columns.setdefault(field_key.strip(), header)
    return columns


def _label(field_key: str) -> str:
    definition = IMPORT_FIELDS_BY_KEY.get(field_key)
    return definition.label if definition is not None else field_key


def validate_mapping(mapping: dict, headers: list[str], options=None) -> MappingCheck:
    """Check a mapping against the file's headers and the chosen options.

    Errors block the import; warnings do not. Every message names the column
    and says how to fix it.
    """
    if options is None:
        options = ImportOptions()
    elif isinstance(options, dict):
        options = ImportOptions.from_dict(options)

    check = MappingCheck()
    mapping = mapping if isinstance(mapping, dict) else {}
    header_set = set(headers)

    by_field: dict[str, list[str]] = {}
    for header, field_key in mapping.items():
        if header not in header_set:
            check.errors.append(
                f"The column '{header}' is in your mapping but not in your file. "
                "Upload the file again and map the columns shown on screen."
            )
            continue
        if _is_ignored(field_key):
            continue
        if not isinstance(field_key, str) or field_key.strip() not in IMPORT_FIELDS_BY_KEY:
            check.errors.append(
                f"The column '{header}' is mapped to '{field_key}', which is not a lead "
                f"field. Pick one of: {_KNOWN_KEYS}, or choose 'Do not import'."
            )
            continue
        by_field.setdefault(field_key.strip(), []).append(header)

    for field_key, columns in by_field.items():
        if len(columns) > 1:
            names = ", ".join(f"'{c}'" for c in columns)
            both = "both" if len(columns) == 2 else "all"
            check.errors.append(
                f"The columns {names} are {both} mapped to {_label(field_key)}. A field can be "
                "filled from only one column. Set the others to 'Do not import' or map "
                "them to different fields; to keep extra information, add them as extra "
                "columns for the description."
            )

    name_ok = "name" in by_field or (
        options.use_company_as_name and "company_name" in by_field
    )
    if not name_ok:
        check.errors.append(
            "Name is required but none of your columns is mapped to it. Map the column "
            "that holds each lead's name to Name, or turn on 'use the company name as "
            "the lead name' and map your company column."
        )

    if not any(key in by_field for key in ("email", *_PHONE_KEYS)):
        check.warnings.append(
            "No column is mapped to Email, Phone or Mobile Number, so duplicates cannot "
            "be detected and every row will be added as new. Map an email or phone "
            "column if your file has one."
        )

    if "owner" in by_field and options.owner_plan.get("mode") != "from_file":
        column = by_field["owner"][0]
        check.warnings.append(
            f"The column '{column}' is mapped to Owner but you chose a different owner "
            "option, so it will be ignored. Choose 'owner from the file' in the owner "
            "step to use it, or set the column to 'Do not import'."
        )

    if "converted" in by_field:
        column = by_field["converted"][0]
        check.warnings.append(
            f"The column '{column}' is mapped to Converted, so rows marked Yes will be "
            "added as an Account and a Contact instead of a lead. If that is not what "
            "you want, set the column to 'Do not import'."
        )

    for extra in options.extra_columns:
        column = extra.get("column")
        if column not in header_set:
            check.warnings.append(
                f"The extra column '{column}' is not in your file, so nothing will be "
                "added to the description for it. Remove it or pick a column from your file."
            )

    return check
