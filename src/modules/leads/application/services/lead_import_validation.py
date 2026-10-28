"""Row validation for lead import, shared with the create flow.

The rules are NOT re-implemented here. A cleaned row is run through
``CreateLeadSerializer`` (the same field validators the create endpoint uses)
and its DRF error codes are translated into import problems. Dropdown values
are checked against a ``PicklistSnapshot`` read once per batch, using the same
rules as ``resolve_option_value`` (picklists/application/services/option_validation.py)
and the same defaults as ``CreateLeadUseCase._option`` (blank -> "None").

``validate_row`` never raises and reports every problem in the row.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field as dataclass_field

# Deliberate reuse of the create flow's validators (see module docstring).
from src.modules.leads.presentation.api.serializers.createLead import (
    CreateLeadSerializer,
)
from src.modules.picklists.application.interfaces.picklist_repository import (
    PicklistRepository,
)
from src.modules.picklists.domain.entities.picklist_catalog import (
    SYSTEM_VALUE,
    get_picklist_field,
)

from .lead_import_fields import (
    IMPORT_FIELDS_BY_KEY,
    KIND_BOOL,
    KIND_EMAIL,
    KIND_INT,
    KIND_OWNER,
    KIND_PHONE,
    KIND_PICKLIST,
    KIND_URL,
    get_field,
)

PICKLIST_MODULE = "leads"
PICKLIST_FIELDS = ("lead_source", "lead_status", "industry", "rating")

MAX_SHOWN_VALUE = 60
MAX_SHOWN_OPTIONS = 10

# Database column limits that CreateLeadSerializer does not enforce, so a
# value that passes the create form could still make a bulk insert fail.
# Source: DjangoLeadModel (EmailField, URLField, PositiveInteger fields).
_INT_LIMITS = {
    "number_of_employees": 2_147_483_647,
    "annual_revenue": 9_223_372_036_854_775_807,
}

_SERIALIZER_FIELDS = frozenset(CreateLeadSerializer().fields)

# Keys of a cleaned row that are not lead columns and must never reach the
# payload: the virtual "owner" and "converted" fields, and any helper key that
# starts with an underscore (e.g. "_extra_phones", used only for duplicates).
_NON_LEAD_KEYS = frozenset({"owner", "converted"})

# Error codes
CODE_REQUIRED = "required"
CODE_TOO_LONG = "too_long"
CODE_INVALID_EMAIL = "invalid_email"
CODE_INVALID_PHONE = "invalid_phone"
CODE_INVALID_URL = "invalid_url"
CODE_INVALID_NUMBER = "invalid_number"
CODE_NEGATIVE_NUMBER = "negative_number"
CODE_UNKNOWN_OPTION = "unknown_option"
CODE_OWNER_NOT_FOUND = "owner_not_found"
CODE_OWNER_INELIGIBLE = "owner_ineligible"
CODE_OWNER_AMBIGUOUS = "owner_ambiguous"
CODE_DUPLICATE = "duplicate"
CODE_CONVERTED_LOCKED = "converted_locked"
CODE_FILE_ERROR = "file_error"
CODE_INVALID_CONVERTED = "invalid_converted"


# ---------------------------------------------------------------------------
# Problem
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RowProblem:
    row_number: int
    column: str
    field: str
    value: object
    code: str
    message: str
    how_to_fix: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Message catalog
# ---------------------------------------------------------------------------

def _show(value: object) -> str:
    """The offending value, on one line and at most 60 characters."""
    text = " ".join(str(value).split()) if value is not None else ""
    if len(text) > MAX_SHOWN_VALUE:
        return text[: MAX_SHOWN_VALUE - 3] + "..."
    return text


def _subject(column: str, value: object) -> str:
    return f"{column} '{_show(value)}'"


def _required(column, value, ctx):
    if ctx.get("unmapped"):
        return (
            f"{column} is required but no column in your file is mapped to it.",
            f"Map one of your file columns to {column} in the column-mapping "
            "step, then check the preview again.",
        )
    return (
        f"{column} is required but this cell is empty.",
        f"Fill in {column} for this row in your file and import again, "
        "or delete the row.",
    )


def _too_long(column, value, ctx):
    limit = ctx.get("max_length")
    length = len(str(value)) if value is not None else 0
    return (
        f"{_subject(column, value)} is {length} characters long; "
        f"the limit is {limit}.",
        f"Shorten it to {limit} characters or fewer.",
    )


def _invalid_email(column, value, ctx):
    return (
        f"{_subject(column, value)} is not valid.",
        "Check for a typo such as a double @ or a missing domain "
        "(for example name@company.com).",
    )


def _invalid_phone(column, value, ctx):
    return (
        f"{_subject(column, value)} does not look like a phone number.",
        "Use digits, optionally with +, spaces, dashes or brackets, "
        "for example +91 98765 43210.",
    )


def _invalid_url(column, value, ctx):
    return (
        f"{_subject(column, value)} is not a valid web address.",
        "Use a full address such as https://www.example.com.",
    )


def _invalid_number(column, value, ctx):
    limit = ctx.get("limit")
    if limit is not None:
        return (
            f"{_subject(column, value)} is too large.",
            f"Use a whole number up to {limit:,}.",
        )
    return (
        f"{_subject(column, value)} is not a valid whole number.",
        "Use digits only, for example 250 or 1500000. Remove any text and decimals.",
    )


def _negative_number(column, value, ctx):
    return (
        f"{_subject(column, value)} is negative.",
        "Use zero or a positive whole number.",
    )


def _unknown_option(column, value, ctx):
    hint = ctx.get("options_hint") or SYSTEM_VALUE
    if ctx.get("hidden"):
        return (
            f"{_subject(column, value)} is no longer available as an option.",
            f"Use one of: {hint}. Or ask a superadmin to turn it back on in Settings.",
        )
    return (
        f"{_subject(column, value)} is not one of your options.",
        f"Use one of: {hint}. Or ask a superadmin to add it in Settings.",
    )


def _owner_not_found(column, value, ctx):
    return (
        f"{_subject(column, value)} does not match any user in your company.",
        "Use the exact email or full name of an active admin or superadmin, "
        "or choose a fallback owner so unmatched rows still import.",
    )


def _owner_ineligible(column, value, ctx):
    return (
        f"{_subject(column, value)} matches a user who cannot own leads.",
        "Only active admins and superadmins can own leads. Use a different "
        "person, or choose a fallback owner.",
    )


def _owner_ambiguous(column, value, ctx):
    return (
        f"{_subject(column, value)} matches more than one user.",
        "Use the person's email address instead of their name.",
    )


def _duplicate(column, value, ctx):
    other = ctx.get("in_file_row")
    if other:
        return (
            f"{_subject(column, value)} is the same as the lead in row {other} of this file.",
            "Delete one of the two rows, or choose 'Create anyway' as the "
            "duplicate action to import both.",
        )
    return (
        f"{_subject(column, value)} matches a lead that already exists.",
        "Choose 'Update' to refresh the existing lead or 'Create anyway' "
        "to add it again; otherwise this row is skipped.",
    )


def _converted_locked(column, value, ctx):
    return (
        f"{_subject(column, value)} matches a lead that was already converted, "
        "and converted leads cannot be changed.",
        "Remove this row, or choose 'Create anyway' to add it as a new lead.",
    )


def _invalid_converted(column, value, ctx):
    return (
        f"{_subject(column, value)} is not Yes or No.",
        "Use Yes or No in this column (leave it blank for No).",
    )


def _file_error(column, value, ctx):
    detail = ctx.get("detail")
    base = "This row could not be read."
    if detail:
        base = f"{base} {detail}"
    return (
        base,
        "Check the row in your file for unusual characters or merged "
        "cells, fix it and upload again.",
    )


# code -> (label shown in the on-screen summary, message builder)
ERROR_CATALOG = {
    CODE_REQUIRED: ("Missing required value", _required),
    CODE_TOO_LONG: ("Value too long", _too_long),
    CODE_INVALID_EMAIL: ("Invalid email", _invalid_email),
    CODE_INVALID_PHONE: ("Invalid phone number", _invalid_phone),
    CODE_INVALID_URL: ("Invalid website address", _invalid_url),
    CODE_INVALID_NUMBER: ("Invalid number", _invalid_number),
    CODE_NEGATIVE_NUMBER: ("Negative number", _negative_number),
    CODE_UNKNOWN_OPTION: ("Not one of your options", _unknown_option),
    CODE_OWNER_NOT_FOUND: ("Owner not found", _owner_not_found),
    CODE_OWNER_INELIGIBLE: ("Owner cannot own leads", _owner_ineligible),
    CODE_OWNER_AMBIGUOUS: ("Owner matches several users", _owner_ambiguous),
    CODE_DUPLICATE: ("Duplicate lead", _duplicate),
    CODE_CONVERTED_LOCKED: ("Matches a converted lead", _converted_locked),
    CODE_FILE_ERROR: ("Row could not be read", _file_error),
    CODE_INVALID_CONVERTED: ("Invalid Converted value", _invalid_converted),
}


def build_problem(
    code: str,
    *,
    row_number: int,
    column: str,
    field: str,
    value: object,
    **context,
) -> RowProblem:
    """A RowProblem with the catalog's plain-English message and fix.

    ``context`` carries code-specific details: ``max_length``, ``limit``,
    ``options_hint``, ``hidden``, ``unmapped``, ``in_file_row``, ``detail``.
    Unknown codes fall back to ``file_error`` so this never raises.
    """
    if code not in ERROR_CATALOG:
        code = CODE_FILE_ERROR
    _, builder = ERROR_CATALOG[code]
    message, how_to_fix = builder(column, value, context)
    return RowProblem(
        row_number=row_number,
        column=column,
        field=field,
        value=value,
        code=code,
        # The row is named in the message itself so it reads on its own.
        message=f"Row {row_number}: {message}",
        how_to_fix=how_to_fix,
    )


def error_groups(problems) -> list[dict]:
    """``[{code, label, count}]`` sorted by count (largest first).

    Accepts RowProblem objects or their stored dicts (``job.problems``).
    """
    counts: dict[str, int] = {}
    for problem in problems:
        code = problem["code"] if isinstance(problem, dict) else problem.code
        counts[code] = counts.get(code, 0) + 1
    groups = [
        {
            "code": code,
            "label": ERROR_CATALOG.get(code, (code.replace("_", " ").capitalize(),))[0],
            "count": count,
        }
        for code, count in counts.items()
    ]
    groups.sort(key=lambda group: (-group["count"], group["label"]))
    return groups


# ---------------------------------------------------------------------------
# Picklists
# ---------------------------------------------------------------------------

@dataclass
class PicklistSnapshot:
    """The company's dropdown options for the four lead picklists.

    Build it ONCE per batch with ``PicklistSnapshot.load`` and pass it to
    every ``validate_row`` call; validating a row never touches the database.

    ``options`` is ``{field: [(value, is_active), ...]}`` in display order.
    """

    options: dict[str, list[tuple[str, bool]]]
    _active: dict[str, dict[str, str]] = dataclass_field(default_factory=dict, repr=False)
    _hidden: dict[str, dict[str, str]] = dataclass_field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for name in PICKLIST_FIELDS:
            entries = self.options.get(name, [])
            self._active[name] = {v.casefold(): v for v, active in entries if active}
            self._hidden[name] = {v.casefold(): v for v, active in entries if not active}

    @classmethod
    def load(cls, repository: PicklistRepository) -> "PicklistSnapshot":
        """Read the four lists: one seeding check plus one query per field
        (inactive options included so a hidden option gets a precise message)."""
        repository.ensure_defaults(PICKLIST_MODULE)
        options = {
            name: [
                (option.value, option.is_active)
                for option in repository.list_options(
                    PICKLIST_MODULE, name, include_inactive=True
                )
            ]
            for name in PICKLIST_FIELDS
        }
        return cls(options=options)

    def label(self, field: str) -> str:
        return get_picklist_field(PICKLIST_MODULE, field).label

    def active_options(self, field: str) -> list[str]:
        return [v for v, active in self.options.get(field, []) if active]

    def options_hint(self, field: str) -> str:
        """"A, B, C, ..." - the first 10 active options, then "..." if more."""
        active = self.active_options(field)
        shown = ", ".join(active[:MAX_SHOWN_OPTIONS])
        if len(active) > MAX_SHOWN_OPTIONS:
            shown += ", ..."
        return shown

    def resolve(self, field: str, raw: object) -> tuple[str | None, str | None]:
        """``(stored_value, None)`` or ``(None, "unknown" | "hidden")``.

        Blank -> "None"; match is case-insensitive and whitespace-insensitive
        and returns the stored spelling (same as resolve_option_value).
        """
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return SYSTEM_VALUE, None
        key = " ".join(str(raw).split()).casefold()
        found = self._active.get(field, {}).get(key)
        if found is not None:
            return found, None
        if key in self._hidden.get(field, {}):
            return None, "hidden"
        return None, "unknown"


# ---------------------------------------------------------------------------
# Row validation
# ---------------------------------------------------------------------------

# DRF error code -> import code, by field kind. Anything else falls back to
# the kind's "invalid" code (or file_error when the kind has none).
_INVALID_CODE_BY_KIND = {
    KIND_EMAIL: CODE_INVALID_EMAIL,
    KIND_PHONE: CODE_INVALID_PHONE,
    KIND_URL: CODE_INVALID_URL,
    KIND_INT: CODE_INVALID_NUMBER,
}


def _translate(drf_code: str, kind: str) -> str:
    if drf_code in {"required", "blank", "null"}:
        return CODE_REQUIRED
    if drf_code == "max_length":
        return CODE_TOO_LONG
    if drf_code == "min_value":
        return CODE_NEGATIVE_NUMBER
    return _INVALID_CODE_BY_KIND.get(kind, CODE_FILE_ERROR)


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def validate_row(
    row_number: int,
    cleaned_values: dict,
    mapping_columns: dict,
    picklists: PicklistSnapshot,
) -> tuple[dict | None, list[RowProblem]]:
    """Validate one cleaned row. Returns ``(payload, problems)``.

    ``cleaned_values``: ``{field_key: cleaned value}`` for this row.
    ``mapping_columns``: ``{field_key: the file's header text}``, used in
    messages. (The job stores file column -> field; invert it once per batch.)

    ``payload`` is ``None`` when there is any problem. Otherwise it holds the
    lead fields ready for ``CreateLeadDTO``: the four dropdowns are always
    present (blank -> "None", as CreateLeadUseCase does), other keys only when
    the row has a value. The ``owner`` virtual field is never part of the
    payload; owner resolution is a separate step. For an *update* the caller
    should apply only the keys of mapped columns, so unmapped dropdowns do not
    reset to "None".

    Never raises.
    """
    try:
        return _validate_row(row_number, cleaned_values, mapping_columns, picklists)
    except Exception:  # noqa: BLE001 - one odd row must never abort a batch
        problem = build_problem(
            CODE_FILE_ERROR,
            row_number=row_number,
            column="",
            field="",
            value=None,
        )
        return None, [problem]


def _column(field_key: str, mapping_columns: dict) -> str:
    header = mapping_columns.get(field_key)
    if header is not None and str(header).strip():
        return str(header).strip()
    definition = get_field(field_key)
    return definition.label if definition is not None else field_key


def _validate_row(row_number, cleaned_values, mapping_columns, picklists):
    problems: list[RowProblem] = []
    values = dict(cleaned_values or {})

    def add(code, field_key, value, **context):
        problems.append(
            build_problem(
                code,
                row_number=row_number,
                column=_column(field_key, mapping_columns),
                field=field_key,
                value=value,
                **context,
            )
        )

    # 1. Dropdowns: checked against the company's options, stored spelling.
    picklist_values: dict[str, str] = {}
    for name in PICKLIST_FIELDS:
        resolved, reason = picklists.resolve(name, values.get(name))
        if reason is None:
            picklist_values[name] = resolved
        else:
            add(
                CODE_UNKNOWN_OPTION,
                name,
                values.get(name),
                options_hint=picklists.options_hint(name),
                hidden=(reason == "hidden"),
            )

    # 2. Everything else goes through the create form's own validators.
    #    Blank values are left out: every one of these fields is optional
    #    except name, which the serializer then reports as "required".
    serializer_data = {
        key: value
        for key, value in values.items()
        if key in _SERIALIZER_FIELDS
        and key not in PICKLIST_FIELDS
        and key not in _NON_LEAD_KEYS
        and not key.startswith("_")
        and not _blank(value)
    }
    serializer = CreateLeadSerializer(data=serializer_data)
    serializer.is_valid()
    failed: set[str] = set()
    for field_key, errors in serializer.errors.items():
        definition = get_field(field_key)
        kind = definition.kind if definition is not None else ""
        drf_code = errors[0].code if errors else "invalid"
        code = _translate(drf_code, kind)
        failed.add(field_key)
        context = {}
        if code == CODE_TOO_LONG and definition is not None:
            context["max_length"] = definition.max_length
        if code == CODE_REQUIRED and field_key not in mapping_columns:
            context["unmapped"] = True
        add(code, field_key, serializer_data.get(field_key), **context)

    # 3. Limits the database enforces but the create form does not.
    for field_key, definition in IMPORT_FIELDS_BY_KEY.items():
        value = serializer_data.get(field_key)
        if field_key in failed or value is None or definition.kind in (KIND_OWNER, KIND_BOOL):
            continue
        if definition.kind == KIND_INT:
            limit = _INT_LIMITS.get(field_key)
            if limit is not None and value > limit:
                add(CODE_INVALID_NUMBER, field_key, value, limit=limit)
        elif (
            definition.kind in {KIND_EMAIL, KIND_URL}
            and definition.max_length
            and len(str(value)) > definition.max_length
        ):
            add(CODE_TOO_LONG, field_key, value, max_length=definition.max_length)
        elif definition.kind == KIND_PHONE and not any(c.isdigit() for c in str(value)):
            # Import-only rule: the create form accepts any text here.
            add(CODE_INVALID_PHONE, field_key, value)

    if problems:
        return None, problems

    payload = {key: serializer.validated_data[key] for key in serializer.validated_data}
    payload.update(picklist_values)
    return payload, []
