"""The shared row pipeline for lead import.

One row in, one ``RowOutcome`` out. Pure application code: no HTTP, no
database writes (the only reads are the ones ``build_context`` does once per
run). The preview, the batch processor and any future Celery task all call
the same ``process_rows``.

Data flow: ``build_context`` reads the company's dropdown options, the
duplicate index and the eligible owners once, and works out from ALL rows
which rows are excluded and which repeat an earlier row of the file (so batch
N still knows a row's first occurrence sits in batch 1). ``process_row`` then
takes each row through exclusion -> cleaning and shaping -> validation ->
duplicate check -> owner assignment -> converted flag. Rows that are skipped,
excluded or rejected never consume the owner rotation, and everything is
deterministic: the same rows and the same starting cursor give the same
outcomes, so a batch can safely be retried. The caller saves
``ctx.owner_cursor`` after each batch.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dataclass_field
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from .lead_import_cleaning import (
    CODE_CLEAN_FAILED,
    CODE_INVALID_CONVERTED,
    CODE_PHONE_CHARS_REMOVED,
    clean_owner,
    clean_value,
    is_blank_like,
)
from .lead_import_duplicates import (
    DUPLICATE_EXISTING,
    DUPLICATE_IN_FILE,
    DuplicateMatch,
    MATCHED_ON_EMAIL,
    classify,
    describe_duplicate,
    duplicate_problem,
    find_in_file_duplicates,
    in_file_match,
)
from .lead_import_fields import IMPORT_FIELDS_BY_KEY, KIND_PHONE
from .lead_import_mapping import IGNORE, mapping_to_columns
from .lead_import_options import ImportOptions
from .lead_import_owners import (
    DEFAULT_OWNER_COLUMN,
    OwnerPlan,
    OwnerResolver,
    OwnerResult,
    load_eligible_owners,
    load_ineligible_users,
    summarize_assignments,
)
from .lead_import_shaping import (
    append_extra_columns,
    apply_phone_splitting,
    apply_value_mapping,
    collect_unrecognized,
    fill_name_from_company,
    split_phones,
)
from .lead_import_validation import (
    CODE_FILE_ERROR,
    CODE_OWNER_AMBIGUOUS,
    CODE_OWNER_INELIGIBLE,
    CODE_OWNER_NOT_FOUND,
    CODE_UNKNOWN_OPTION,
    PICKLIST_FIELDS,
    PicklistSnapshot,
    RowProblem,
    build_problem,
    error_groups,
    validate_row,
)

logger = logging.getLogger(__name__)

# Outcome statuses
READY = "ready"
DUPLICATE_SKIP = "duplicate_skip"
DUPLICATE_UPDATE = "duplicate_update"
DUPLICATE_CREATE = "duplicate_create"
EXCLUDED = "excluded"
ERROR = "error"
CONVERT = "convert"  # a ready row that goes to Account + Contact
STATUSES = (
    READY, DUPLICATE_SKIP, DUPLICATE_UPDATE, DUPLICATE_CREATE, EXCLUDED, ERROR, CONVERT,
)

SKIPPED_FOR_ERRORS = "Skipped because it has errors"
MAX_ERROR_GROUPS = 10

_OWNER_PROBLEM_CODES = frozenset(
    {CODE_OWNER_NOT_FOUND, CODE_OWNER_INELIGIBLE, CODE_OWNER_AMBIGUOUS}
)
_PHONE_FIELDS = ("mobile_number", "phone")

_OPERATOR_WORDS = {
    "is_blank": "is blank",
    "is_not_blank": "is not blank",
    "equals": "equals",
    "not_equals": "does not equal",
    "contains": "contains",
    "not_contains": "does not contain",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _json_safe(value):
    """Plain JSON types only, so outcomes can live in job.problems or an API
    response."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(v) for v in value]
    return str(value)


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _loose(value) -> str:
    return " ".join(str(value).split()).casefold() if value is not None else ""


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _row_values(row) -> dict:
    """The row's file values; an unreadable row gives an empty dict."""
    try:
        values = row.get("values")
        if values is None:
            values = row.get("original")
        return dict(values or {})
    except Exception:  # noqa: BLE001 - must never raise, it is used in error handling
        return {}


# ---------------------------------------------------------------------------
# Outcome
# ---------------------------------------------------------------------------

def _problem_from_dict(data: dict) -> RowProblem:
    return RowProblem(
        row_number=data.get("row_number", 0),
        column=data.get("column", ""),
        field=data.get("field", ""),
        value=data.get("value"),
        code=data.get("code", CODE_FILE_ERROR),
        message=data.get("message", ""),
        how_to_fix=data.get("how_to_fix", ""),
    )


def _duplicate_to_dict(match: DuplicateMatch | None) -> dict | None:
    if match is None:
        return None
    return {
        "kind": match.kind,
        "matched_on": match.matched_on,
        "lead_id": None if match.lead_id is None else str(match.lead_id),
        "name": match.name,
        "is_converted": bool(match.is_converted),
        "first_row": match.first_row,
    }


def _duplicate_from_dict(data: dict | None) -> DuplicateMatch | None:
    if not data:
        return None
    return DuplicateMatch(
        kind=data.get("kind", DUPLICATE_EXISTING),
        matched_on=data.get("matched_on"),
        lead_id=data.get("lead_id"),
        name=data.get("name"),
        is_converted=bool(data.get("is_converted")),
        first_row=data.get("first_row"),
    )


@dataclass
class RowOutcome:
    row_number: int
    status: str = ERROR
    # The validated lead fields (never owner / converted / underscore keys).
    # For DUPLICATE_UPDATE only the keys that should change (mapped columns and
    # fields derived from them); blank cells never overwrite existing values.
    payload: dict | None = None
    owner_id: str | None = None
    owner_source: str | None = None
    is_converted: bool = False
    duplicate: DuplicateMatch | None = None
    matched_lead_id: str | None = None
    problems: list[RowProblem] = dataclass_field(default_factory=list)
    warnings: list[dict] = dataclass_field(default_factory=list)  # [{code, message}]
    # Why the row was excluded (EXCLUDED only).
    reason: str | None = None
    # The untouched file values, so rejected rows can be written back out.
    original_values: dict = dataclass_field(default_factory=dict)

    def to_dict(self, include_original: bool = True) -> dict:
        data = {
            "row_number": self.row_number,
            "status": self.status,
            "payload": _json_safe(self.payload),
            "owner_id": self.owner_id,
            "owner_source": self.owner_source,
            "is_converted": self.is_converted,
            "duplicate": _duplicate_to_dict(self.duplicate),
            "matched_lead_id": self.matched_lead_id,
            "problems": [_json_safe(p.to_dict()) for p in self.problems],
            "warnings": [_json_safe(w) for w in self.warnings],
            "reason": self.reason,
        }
        if include_original:
            data["original_values"] = _json_safe(self.original_values)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "RowOutcome":
        return cls(
            row_number=data.get("row_number", 0),
            status=data.get("status", ERROR),
            payload=data.get("payload"),
            owner_id=data.get("owner_id"),
            owner_source=data.get("owner_source"),
            is_converted=bool(data.get("is_converted")),
            duplicate=_duplicate_from_dict(data.get("duplicate")),
            matched_lead_id=data.get("matched_lead_id"),
            problems=[_problem_from_dict(p) for p in data.get("problems") or []],
            warnings=[dict(w) for w in data.get("warnings") or []],
            reason=data.get("reason"),
            original_values=dict(data.get("original_values") or {}),
        )


# ---------------------------------------------------------------------------
# Exclusions
# ---------------------------------------------------------------------------

def _rule_matches(rule: dict, row_values: dict) -> bool:
    operator = rule.get("operator")
    cell = row_values.get(rule.get("column"))
    text = _loose(cell)

    if operator == "is_blank":
        return text == "" or is_blank_like(text)
    if operator == "is_not_blank":
        return not (text == "" or is_blank_like(text))

    options = [_loose(part) for part in str(rule.get("value") or "").split("|")]
    options = [part for part in options if part]
    if not options:
        return False
    if operator == "equals":
        return any(text == part for part in options)
    if operator == "not_equals":
        return not any(text == part for part in options)
    if operator == "contains":
        return any(part in text for part in options)
    if operator == "not_contains":
        return not any(part in text for part in options)
    return False


def is_excluded(row_values: dict, row_number: int, exclusions: dict | None):
    """``(True, reason)`` when the row is excluded by number or by a rule.

    Rules compare trimmed, case-insensitive text. For ``equals`` and
    ``contains`` the rule value may hold several options separated by ``|``
    (any one matching is enough); ``not_equals`` / ``not_contains`` are the
    exact opposite (none of the options may match). ``skip_rows_with_errors``
    is applied later by ``process_rows``.
    """
    exclusions = exclusions or {}
    if row_number in set(exclusions.get("row_numbers") or []):
        return True, "You excluded this row."
    for rule in exclusions.get("rules") or []:
        if _rule_matches(rule, row_values or {}):
            words = _OPERATOR_WORDS.get(rule.get("operator"), rule.get("operator"))
            parts = [p.strip() for p in str(rule.get("value") or "").split("|") if p.strip()]
            tail = (" " + " or ".join(f"'{p}'" for p in parts)) if parts else ""
            return True, f"Excluded by your rule: {rule.get('column')} {words}{tail}."
    return False, None


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

@dataclass
class PipelineRepositories:
    lead_repository: object
    user_repository: object
    picklist_repository: object


@dataclass
class PipelineContext:
    options: ImportOptions
    plan: OwnerPlan
    mapping: dict  # {header: field key}, ignored columns removed
    mapping_columns: dict  # {field key: header}
    picklists: PicklistSnapshot
    dedupe_index: dict
    eligible_owners: list
    ineligible_users: list
    resolver: OwnerResolver
    current_user_id: object
    start_cursor: int = 0
    in_file: dict = dataclass_field(default_factory=dict)  # {row: first row}
    excluded: dict = dataclass_field(default_factory=dict)  # {row: reason}
    known_rows: frozenset = frozenset()

    @property
    def owner_cursor(self) -> int:
        """Save this after each batch (``job.options["round_robin_cursor"]``)
        and it is read back by ``build_context`` for the next one."""
        return self.resolver.cursor

    @property
    def excluded_row_numbers(self) -> set[int]:
        return set(self.excluded)


def _read_cursor(raw_options, job) -> int:
    candidates = []
    if isinstance(raw_options, dict):
        candidates.append(raw_options.get("round_robin_cursor"))
        plan = raw_options.get("owner_plan")
        if isinstance(plan, dict):
            candidates.append(plan.get("round_robin_cursor"))
    candidates.append(_get(job, "round_robin_cursor"))
    for value in candidates:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return 0


def _clean_mapping(raw_mapping) -> dict:
    mapping = {}
    if isinstance(raw_mapping, dict):
        for header, field_key in raw_mapping.items():
            if not isinstance(field_key, str) or field_key.strip() in ("", IGNORE):
                continue
            if field_key.strip() in IMPORT_FIELDS_BY_KEY:
                mapping[header] = field_key.strip()
    return mapping


def build_context(job_like, tenant_context, repositories) -> PipelineContext:
    """Everything a run needs, read once. Cheap enough to rebuild at the start
    of every batch (a handful of queries plus one light pass over the rows).

    ``job_like`` has ``headers``, ``mapping``, ``options`` and ``rows`` (the
    job's stored ``[{row_number, values}]``); attributes or dict keys both
    work. ``repositories`` has ``lead_repository``, ``user_repository`` and
    ``picklist_repository``.
    """
    raw_options = _get(job_like, "options")
    options = (
        raw_options if isinstance(raw_options, ImportOptions)
        else ImportOptions.from_dict(raw_options)
    )
    plan = OwnerPlan.from_dict(options.owner_plan)
    mapping = _clean_mapping(_get(job_like, "mapping"))
    mapping_columns = mapping_to_columns(mapping)

    picklists = PicklistSnapshot.load(repositories.picklist_repository)
    dedupe_index = repositories.lead_repository.get_dedupe_index()
    eligible = load_eligible_owners(tenant_context, repositories.user_repository)
    ineligible = (
        load_ineligible_users(tenant_context, repositories.user_repository, eligible)
        if plan.mode == "from_file"
        else []
    )

    cursor = _read_cursor(raw_options, job_like)
    resolver = OwnerResolver(
        plan,
        eligible,
        tenant_context.user_id,
        cursor=cursor,
        ineligible_users=ineligible,
        owner_column=mapping_columns.get("owner") or DEFAULT_OWNER_COLUMN,
    )

    ctx = PipelineContext(
        options=options,
        plan=plan,
        mapping=mapping,
        mapping_columns=mapping_columns,
        picklists=picklists,
        dedupe_index=dedupe_index,
        eligible_owners=eligible,
        ineligible_users=ineligible,
        resolver=resolver,
        current_user_id=tenant_context.user_id,
        start_cursor=cursor,
    )

    rows = _get(job_like, "rows") or []
    ctx.known_rows = frozenset(row["row_number"] for row in rows)
    candidates = []
    for row in rows:
        values = _row_values(row)
        excluded, reason = is_excluded(values, row["row_number"], options.exclusions)
        if excluded:
            ctx.excluded[row["row_number"]] = reason
            continue
        cleaned = _clean_row(row["row_number"], values, ctx)[0]
        candidates.append({"row_number": row["row_number"], "cleaned": cleaned})
    # Excluded rows are left out, so an excluded first occurrence never
    # swallows a later row. The first occurrence is kept even when it is later
    # rejected for another reason; it then shows up in the rejected rows.
    ctx.in_file = find_in_file_duplicates(candidates)
    return ctx


# ---------------------------------------------------------------------------
# Cleaning and shaping
# ---------------------------------------------------------------------------

def _warn(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def _clean_row(row_number: int, values: dict, ctx: PipelineContext):
    """Steps b + c: ``(cleaned, derived_keys, warnings, problems)``."""
    options = ctx.options
    mapped_keys = set(ctx.mapping_columns)
    cleaned: dict = {}
    warnings: list[dict] = []
    problems: list[RowProblem] = []

    for field_key, header in ctx.mapping_columns.items():
        definition = IMPORT_FIELDS_BY_KEY[field_key]
        raw = values.get(header)
        value, code = clean_value(definition.kind, raw, multiline=definition.multiline)
        cleaned[field_key] = value
        if code == CODE_INVALID_CONVERTED:
            problems.append(
                build_problem(
                    CODE_INVALID_CONVERTED, row_number=row_number, column=header,
                    field=field_key, value=value,
                )
            )
        elif code == CODE_PHONE_CHARS_REMOVED:
            splitting = options.split_multiple_phones and len(split_phones(raw)) > 1
            if not splitting:
                warnings.append(
                    _warn(code, f"Characters that are not part of a phone number were "
                                f"removed from {header} '{raw}'.")
                )
        elif code == CODE_CLEAN_FAILED:
            warnings.append(
                _warn(code, f"The value in {header} could not be tidied up and was "
                            "kept as written.")
            )
    before = dict(cleaned)

    if options.split_multiple_phones and any(f in mapped_keys for f in _PHONE_FIELDS):
        raw_phones = {
            f: values.get(ctx.mapping_columns[f])
            for f in _PHONE_FIELDS
            if f in ctx.mapping_columns
            and IMPORT_FIELDS_BY_KEY[f].kind == KIND_PHONE
        }
        cleaned, found = apply_phone_splitting(cleaned, mapped_keys, raw_phones)
        warnings.extend(_warn(w["code"], w["message"]) for w in found)

    if options.use_company_as_name:
        cleaned = fill_name_from_company(cleaned)

    if options.extra_columns:
        description, found = append_extra_columns(
            cleaned.get("description"), values, options.extra_columns
        )
        if description != cleaned.get("description"):
            cleaned["description"] = description
        warnings.extend(_warn(w["code"], w["message"]) for w in found)

    for field_key in PICKLIST_FIELDS:
        if field_key in cleaned:
            cleaned[field_key] = apply_value_mapping(
                field_key, cleaned[field_key], options, ctx.picklists
            )

    derived = {
        key
        for key, value in cleaned.items()
        if not key.startswith("_")
        and key not in mapped_keys
        and value != before.get(key)
    }
    return cleaned, derived, warnings, problems


def _update_payload(payload: dict, cleaned: dict, ctx: PipelineContext, derived: set) -> dict:
    """What an UPDATE may change: mapped columns (and fields filled from them)
    that actually hold a value. A blank cell never wipes an existing value and
    an unmapped dropdown is never reset to "None"."""
    allowed = set(ctx.mapping_columns) | derived
    result = {}
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key in PICKLIST_FIELDS and _blank(cleaned.get(key)):
            continue
        result[key] = value
    return result


# ---------------------------------------------------------------------------
# One row
# ---------------------------------------------------------------------------

def _duplicate_column_value(match: DuplicateMatch, cleaned: dict, ctx: PipelineContext):
    if match.matched_on == MATCHED_ON_EMAIL:
        return ctx.mapping_columns.get("email", "Email"), "email", cleaned.get("email")
    for field_key in _PHONE_FIELDS:
        if not _blank(cleaned.get(field_key)):
            return ctx.mapping_columns.get(field_key, field_key), field_key, cleaned.get(field_key)
    return "Phone", "phone", None


def process_row(row: dict, ctx: PipelineContext) -> RowOutcome:
    """Takes one stored row through the whole pipeline. Never raises."""
    row_number = row.get("row_number", 0) if isinstance(row, dict) else 0
    try:
        return _process_row(row, ctx)
    except Exception:  # noqa: BLE001 - one odd row must never abort a batch
        logger.exception("Lead import: unexpected problem with row %s", row_number)
        problem = build_problem(
            CODE_FILE_ERROR, row_number=row_number, column="", field="", value=None,
            detail="Unexpected problem with this row.",
        )
        values = _row_values(row) if isinstance(row, dict) else {}
        return RowOutcome(
            row_number=row_number, status=ERROR, problems=[problem], original_values=values
        )


def _process_row(row: dict, ctx: PipelineContext) -> RowOutcome:
    row_number = row["row_number"]
    values = _row_values(row)
    outcome = RowOutcome(row_number=row_number, original_values=values)
    options = ctx.options

    # a. excluded
    reason = ctx.excluded.get(row_number)
    if reason is None and row_number not in ctx.known_rows:
        excluded, reason = is_excluded(values, row_number, options.exclusions)
        reason = reason if excluded else None
    if reason is not None:
        outcome.status = EXCLUDED
        outcome.reason = reason
        return outcome

    # b + c. clean and shape
    cleaned, derived, warnings, cleaning_problems = _clean_row(row_number, values, ctx)
    outcome.warnings = warnings

    # d. validate
    payload, problems = validate_row(
        row_number, cleaned, ctx.mapping_columns, ctx.picklists
    )
    problems = cleaning_problems + list(problems)
    if problems or payload is None:
        outcome.status = ERROR
        outcome.problems = problems
        return outcome

    # e. duplicates
    action = options.duplicate_action
    status = READY
    match: DuplicateMatch | None = None
    first_row = ctx.in_file.get(row_number)
    if first_row is not None:
        match = in_file_match(first_row, cleaned)
        if action == "create_anyway":
            status = DUPLICATE_CREATE
        else:
            return _skip(outcome, match, "duplicate_in_file")
    else:
        found = classify(cleaned, ctx.dedupe_index)
        if found.kind == DUPLICATE_EXISTING:
            match = found
            outcome.matched_lead_id = None if found.lead_id is None else str(found.lead_id)
            if action == "create_anyway":
                status = DUPLICATE_CREATE
            elif action == "update":
                if found.is_converted:
                    column, field_key, value = _duplicate_column_value(found, cleaned, ctx)
                    outcome.problems.append(
                        duplicate_problem(
                            found, row_number=row_number, column=column,
                            field=field_key, value=value,
                        )
                    )
                    return _skip(outcome, match, "duplicate")
                status = DUPLICATE_UPDATE
            else:
                return _skip(outcome, match, "duplicate")
    outcome.duplicate = match
    outcome.payload = (
        _update_payload(payload, cleaned, ctx, derived)
        if status == DUPLICATE_UPDATE
        else payload
    )

    # f. owner (only rows that create a lead, or update one when asked to)
    takes_owner = status in (READY, DUPLICATE_CREATE) or (
        status == DUPLICATE_UPDATE and ctx.plan.change_owner_on_update
    )
    if takes_owner:
        result = ctx.resolver.resolve(row_number, cleaned.get("owner"))
        if isinstance(result, RowProblem):
            outcome.status = ERROR
            outcome.payload = None
            outcome.problems = [result]
            return outcome
        _apply_owner(outcome, result)

    # g. converted (new rows only; an existing lead is never converted)
    if cleaned.get("converted") is True and status in (READY, DUPLICATE_CREATE):
        status = CONVERT
        outcome.is_converted = True

    outcome.status = status
    return outcome


def _skip(outcome: RowOutcome, match: DuplicateMatch, code: str) -> RowOutcome:
    outcome.status = DUPLICATE_SKIP
    outcome.duplicate = match
    if match.kind == DUPLICATE_EXISTING and match.lead_id is not None:
        outcome.matched_lead_id = str(match.lead_id)
    outcome.warnings.append(_warn(code, describe_duplicate(match)[0]))
    return outcome


def _apply_owner(outcome: RowOutcome, result: OwnerResult) -> None:
    outcome.owner_id = str(result.owner_id)
    outcome.owner_source = result.source
    if result.warning is not None:
        outcome.warnings.append(_warn(result.warning.code, result.warning.message))


# ---------------------------------------------------------------------------
# Many rows
# ---------------------------------------------------------------------------

def process_rows(rows, ctx: PipelineContext) -> list[RowOutcome]:
    """Rows are processed strictly in the order given (the order decides the
    owner rotation). Afterwards ``ctx.owner_cursor`` holds the cursor to save."""
    outcomes = [process_row(row, ctx) for row in rows]
    if ctx.options.exclusions.get("skip_rows_with_errors"):
        for outcome in outcomes:
            if outcome.status == ERROR:
                outcome.status = EXCLUDED
                outcome.reason = SKIPPED_FOR_ERRORS
    return outcomes


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _error_problems(outcome: RowOutcome) -> list[RowProblem]:
    """Problems that mean "this row has an error" (not a converted-lead note
    attached to a skipped duplicate)."""
    if outcome.status == ERROR or (
        outcome.status == EXCLUDED and outcome.reason == SKIPPED_FOR_ERRORS
    ):
        return list(outcome.problems)
    return []


def summarize(outcomes, ctx: PipelineContext | None = None) -> dict:
    """Counts and groups for the check screen and the final report.

    With ``ctx`` the summary also carries the owner assignment summary (via
    ``summarize_assignments``, starting from the cursor the run started with)
    and the unrecognised dropdown values with suggestions.
    """
    outcomes = list(outcomes)
    counts = {status: 0 for status in STATUSES}
    duplicates = {"existing": 0, "in_file": 0, "converted_locked": 0}
    problems: list[RowProblem] = []
    for outcome in outcomes:
        counts[outcome.status] = counts.get(outcome.status, 0) + 1
        problems.extend(_error_problems(outcome))
        match = outcome.duplicate
        if match is not None and outcome.status == DUPLICATE_SKIP:
            if match.kind == DUPLICATE_IN_FILE:
                duplicates["in_file"] += 1
            elif match.is_converted:
                duplicates["converted_locked"] += 1
            else:
                duplicates["existing"] += 1

    summary = {
        "total": len(outcomes),
        "counts": counts,
        "converted": sum(1 for o in outcomes if o.is_converted),
        "duplicates_skipped": duplicates,
        "error_groups": error_groups(problems)[:MAX_ERROR_GROUPS],
        "owners": None,
        "unrecognized": {},
    }
    if ctx is None:
        return summary

    owner_header = ctx.mapping_columns.get("owner")
    owner_rows = []
    for outcome in outcomes:
        owner_error = any(p.code in _OWNER_PROBLEM_CODES for p in outcome.problems)
        if outcome.owner_id is None and not (outcome.status == ERROR and owner_error):
            continue
        cell, _warning = clean_owner(outcome.original_values.get(owner_header)) if owner_header else (None, None)
        owner_rows.append({"row_number": outcome.row_number, "cleaned": {"owner": cell}})
    summary["owners"] = summarize_assignments(
        ctx.plan,
        ctx.eligible_owners,
        ctx.current_user_id,
        owner_rows,
        cursor=ctx.start_cursor,
        ineligible_users=ctx.ineligible_users,
        owner_column=owner_header or DEFAULT_OWNER_COLUMN,
    )

    unknown = [
        p for o in outcomes for p in o.problems if p.code == CODE_UNKNOWN_OPTION
    ]
    fields = sorted({p.field for p in unknown})
    summary["unrecognized"] = collect_unrecognized(
        [{p.field: p.value} for p in unknown], fields, ctx.picklists
    )
    return summary
