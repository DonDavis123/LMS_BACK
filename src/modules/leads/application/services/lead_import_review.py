"""Shared helpers for the import review endpoints (upload, preview, check, rows).

Pure Python, no HTTP and no database access.

A draft job keeps its check result in two places:

* ``job.problems``: one compact dict per row that is NOT plain READY (errors,
  duplicates, excluded and converted rows). READY rows are not stored; they
  are recomputed when the import runs.
* ``job.options["last_check"]``: the summary, the counts and a fingerprint of
  the mapping and options the check was made with. When the saved mapping or
  options no longer match that fingerprint, the check is outdated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .lead_import_mapping import IGNORE, mapping_to_columns
from .lead_import_parser import DEFAULT_MAX_BYTES, DEFAULT_MAX_ROWS
from .lead_import_pipeline import (
    CONVERT,
    DUPLICATE_CREATE,
    DUPLICATE_SKIP,
    DUPLICATE_UPDATE,
    ERROR,
    EXCLUDED,
    READY,
    SKIPPED_FOR_ERRORS,
    RowOutcome,
)

STAGE_DRAFT = "draft"

# Keys the server owns inside job.options. They are never taken from a request.
SERVER_OPTION_KEYS = frozenset({"stage", "last_check", "round_robin_cursor"})

# Row filters of the rows endpoint.
FILTER_ALL = "all"
FILTER_READY = "ready"
FILTER_DUPLICATE = "duplicate"
FILTER_ERROR = "error"
FILTER_EXCLUDED = "excluded"
FILTER_CONVERTED = "converted"
ROW_FILTERS = (
    FILTER_ALL, FILTER_READY, FILTER_DUPLICATE, FILTER_ERROR, FILTER_EXCLUDED,
    FILTER_CONVERTED,
)

PREVIEW_ROW_COUNT = 15
SAMPLE_ROW_COUNT = 5
MAX_PROBLEMS_SHOWN = 20
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25
MAX_SEARCH_LENGTH = 100

# Statuses of rows that will be written when the import runs.
_IMPORTABLE = (READY, CONVERT, DUPLICATE_UPDATE, DUPLICATE_CREATE)


def import_limits() -> dict:
    """The upload limits in force (settings override the defaults)."""
    max_bytes, max_rows = DEFAULT_MAX_BYTES, DEFAULT_MAX_ROWS
    try:
        from django.conf import settings

        max_bytes = int(getattr(settings, "LEAD_IMPORT_MAX_BYTES", max_bytes))
        max_rows = int(getattr(settings, "LEAD_IMPORT_MAX_ROWS", max_rows))
    except Exception:  # noqa: BLE001 - Django not configured (scripts)
        pass
    return {
        "max_bytes": max_bytes,
        "max_rows": max_rows,
        "allowed_extensions": [".csv", ".xlsx"],
    }


def to_jsonable(value):
    """A copy made of plain JSON types only."""
    return json.loads(json.dumps(value, default=str))


# ---------------------------------------------------------------------------
# Mapping and options as stored on the draft
# ---------------------------------------------------------------------------

def sanitize_mapping(raw, headers: list[str]) -> dict:
    """``{header: field key | "__ignore__"}`` for the file's own headers only.

    Anything that is not a string becomes text so ``validate_mapping`` can
    explain it; headers that are not in the file are dropped (they have
    already been reported by the validation that ran before this).
    """
    header_set = set(headers)
    result = {}
    if isinstance(raw, dict):
        for header, value in raw.items():
            if header not in header_set:
                continue
            if value is None:
                result[header] = IGNORE
            elif isinstance(value, str):
                result[header] = value.strip() or IGNORE
            else:
                result[header] = str(value)[:100]
    return result


def client_options(stored_options) -> dict:
    """The user-editable part of the stored options."""
    if not isinstance(stored_options, dict):
        return {}
    return {k: v for k, v in stored_options.items() if k not in SERVER_OPTION_KEYS}


def with_server_keys(options: dict, stored_options) -> dict:
    """``options`` plus the server-owned keys already on the job."""
    merged = dict(options)
    if isinstance(stored_options, dict):
        for key in SERVER_OPTION_KEYS:
            if key in stored_options:
                merged[key] = stored_options[key]
    return merged


def fingerprint(mapping, options) -> str:
    """Identifies the mapping + options a check was made with."""
    payload = json.dumps(
        {"mapping": mapping or {}, "options": client_options(options)},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_draft(job) -> bool:
    options = job.options if isinstance(job.options, dict) else {}
    return (
        job.status == "queued"
        and not job.processed_rows
        and options.get("stage") == STAGE_DRAFT
    )


def last_check(job) -> dict | None:
    options = job.options if isinstance(job.options, dict) else {}
    check = options.get("last_check")
    return check if isinstance(check, dict) else None


def check_is_current(job) -> bool:
    check = last_check(job)
    return bool(check) and check.get("fingerprint") == fingerprint(job.mapping, job.options)


# ---------------------------------------------------------------------------
# Compact outcomes (what is kept in job.problems)
# ---------------------------------------------------------------------------

def compact_outcome(outcome: RowOutcome, owner_names: dict) -> dict:
    """An outcome without its payload and original values (the rows are on the
    job already), and without empty keys, to keep 10,000 rows small."""
    data = outcome.to_dict(include_original=False)
    data.pop("payload", None)
    for key in (
        "owner_id", "owner_source", "duplicate", "matched_lead_id", "reason",
    ):
        if data.get(key) is None:
            data.pop(key, None)
    for key in ("problems", "warnings"):
        if not data.get(key):
            data.pop(key, None)
    if not data.get("is_converted"):
        data.pop("is_converted", None)
    if outcome.owner_id is not None and owner_names.get(outcome.owner_id):
        data["owner_name"] = owner_names[outcome.owner_id]
    return data


def stored_row_problems(stored: dict) -> list[dict]:
    """The problems that make a stored row an error row."""
    if stored.get("status") == ERROR or (
        stored.get("status") == EXCLUDED and stored.get("reason") == SKIPPED_FOR_ERRORS
    ):
        return list(stored.get("problems") or [])
    return []


def importable_count(counts: dict) -> int:
    return sum(int(counts.get(status, 0)) for status in _IMPORTABLE)


def categories(status: str, has_duplicate: bool) -> set[str]:
    """Filters a row with this status belongs to (a row can be in two:
    converted rows are also ready rows)."""
    if status in (READY, CONVERT):
        found = {FILTER_READY}
        if status == CONVERT:
            found.add(FILTER_CONVERTED)
            if has_duplicate:
                found.add(FILTER_DUPLICATE)
        return found
    if status in (DUPLICATE_SKIP, DUPLICATE_UPDATE, DUPLICATE_CREATE):
        return {FILTER_DUPLICATE}
    if status == ERROR:
        return {FILTER_ERROR}
    if status == EXCLUDED:
        return {FILTER_EXCLUDED}
    return set()


# ---------------------------------------------------------------------------
# API shapes
# ---------------------------------------------------------------------------

def values_by_field(values: dict, mapping: dict) -> dict:
    """The row's raw cell text under the field each column is mapped to."""
    return {
        field_key: values.get(header)
        for field_key, header in mapping_to_columns(mapping).items()
    }


def public_row(stored: dict, values: dict, mapping: dict) -> dict:
    """One row of the rows endpoint. ``stored`` is a compact outcome."""
    owner = None
    if stored.get("owner_id"):
        owner = {
            "id": stored["owner_id"],
            "name": stored.get("owner_name"),
            "source": stored.get("owner_source"),
        }
    return {
        "row_number": stored["row_number"],
        "status": stored["status"],
        "is_converted": bool(stored.get("is_converted")),
        "values": values,
        "values_by_field": values_by_field(values, mapping),
        "owner": owner,
        "duplicate": stored.get("duplicate"),
        "reason": stored.get("reason"),
        "problems": stored.get("problems") or [],
        "warnings": stored.get("warnings") or [],
    }


def ready_row(row_number: int) -> dict:
    return {"row_number": row_number, "status": READY}


def row_is_blank(values: dict) -> bool:
    return not any(str(v).strip() for v in (values or {}).values() if v is not None)




@dataclass(frozen=True)
class RowQuery:
    status: str = FILTER_ALL
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    search: str = ""
