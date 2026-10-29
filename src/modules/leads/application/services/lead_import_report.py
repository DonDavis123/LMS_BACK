"""The report of a finished lead import, and the plain-English text of each row.

Pure Python: no Django, no HTTP, no database access. It reads what the
processor stored on the job:

* ``job.problems``: one compact entry per row that is NOT a plainly created
  lead (``row_number``, ``status``, ``result``, ``note``, ``reason``,
  ``problems``, ``warnings``, ``duplicate``, ``owner_name`` and, while the file
  has few problem rows, ``original_values``);
* ``job.options``: the counters, ``converted``, ``row_owners`` (see
  ``record_row_owners``), ``value_mapping`` and ``last_check``.

``build_report_summary`` freezes the numbers into ``options["report_summary"]``
when the import ends, so the report keeps working after the stored rows are
purged. Every function here is deterministic and safe to call twice.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone

from .lead_import_conversion import converted_count
from .lead_import_duplicates import (
    DUPLICATE_EXISTING,
    DUPLICATE_IN_FILE,
    MATCHED_ON_EMAIL,
    MATCHED_ON_PHONE,
)
from .lead_import_undo import undo_eligibility
from .lead_import_pipeline import (
    DUPLICATE_SKIP,
    ERROR,
    EXCLUDED,
    SKIPPED_FOR_ERRORS,
)
from .lead_import_validation import ERROR_CATALOG, error_groups

# What happened to a row (the "Result" column of the results file).
CATEGORY_ADDED = "added"
CATEGORY_UPDATED = "updated"
CATEGORY_CONVERTED = "converted"
CATEGORY_SKIPPED_DUPLICATE = "skipped_duplicate"
CATEGORY_NEEDS_ATTENTION = "needs_attention"
CATEGORY_EXCLUDED = "excluded"

RESULT_LABELS = {
    CATEGORY_ADDED: "Added",
    CATEGORY_UPDATED: "Updated",
    CATEGORY_SKIPPED_DUPLICATE: "Skipped duplicate",
    CATEGORY_NEEDS_ATTENTION: "Needs attention",
    CATEGORY_EXCLUDED: "Excluded",
    CATEGORY_CONVERTED: "Converted to account and contact",
}

STAGE_FINISHED = "finished"
STAGE_CANCELLED = "cancelled"
STAGE_FAILED = "failed"

MAX_EXAMPLE_ROWS = 5
MAX_GROUPS = 30
MAX_WARNING_GROUPS = 20
MAX_MAPPED_VALUES = 100
MAX_TOP_ERROR_GROUPS = 10
MAX_TEXT = 1000
BLANK_VALUE = "__blank__"

_ROW_PREFIX = re.compile(r"^Row\s+\d+:\s*")
_BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"
_MAX_OWNERS = 36 * 36 - 1


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _options(job) -> dict:
    return job.options if isinstance(job.options, dict) else {}


def _entries(job) -> list[dict]:
    return [entry for entry in (job.problems or []) if isinstance(entry, dict)]


def _clip(text: str, limit: int = MAX_TEXT) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def to_jsonable(value):
    return json.loads(json.dumps(value, default=str))


def duration_seconds(job) -> int | None:
    if job.started_at is None or job.finished_at is None:
        return None
    return max(0, int((job.finished_at - job.started_at).total_seconds()))


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


# ---------------------------------------------------------------------------
# Which owner each row got (kept compactly, READY rows are not stored)
# ---------------------------------------------------------------------------

def _encode(number: int) -> str:
    return _BASE36[number // 36] + _BASE36[number % 36]


def record_row_owners(options: dict, start: int, owners: list) -> dict:
    """``options`` with the owners of one batch added; the input is unchanged.

    ``owners`` has one item per row of the batch, in file order: ``None`` or an
    ``(owner_id, owner_name)`` pair. The result keeps ``{"ids", "names",
    "codes"}`` where ``codes`` holds two characters per row position (``00`` =
    no owner, else the owner's index + 1 in base 36), so 10,000 rows take
    about 20 KB. The codes are cut back to ``start`` first, so redoing a batch
    can never shift later rows.
    """
    stored = options.get("row_owners") if isinstance(options.get("row_owners"), dict) else {}
    ids = list(stored.get("ids") or [])
    names = list(stored.get("names") or [])
    codes = str(stored.get("codes") or "")[: start * 2].ljust(start * 2, "0")

    pieces = []
    for owner in owners:
        if not owner or not owner[0]:
            pieces.append("00")
            continue
        owner_id, owner_name = str(owner[0]), str(owner[1] or "")
        if owner_id not in ids:
            if len(ids) >= _MAX_OWNERS:
                pieces.append("00")
                continue
            ids.append(owner_id)
            names.append(owner_name)
        pieces.append(_encode(ids.index(owner_id) + 1))

    updated = dict(options)
    updated["row_owners"] = {"ids": ids, "names": names, "codes": codes + "".join(pieces)}
    return updated


def owner_name_at(options: dict, position: int) -> str | None:
    """The owner name of the row at this 0-based position in the file."""
    stored = options.get("row_owners") if isinstance(options, dict) else None
    if not isinstance(stored, dict):
        return None
    codes = str(stored.get("codes") or "")
    chunk = codes[position * 2: position * 2 + 2]
    if len(chunk) != 2:
        return None
    try:
        number = _BASE36.index(chunk[0]) * 36 + _BASE36.index(chunk[1])
    except ValueError:
        return None
    names = stored.get("names") or []
    return names[number - 1] if 0 < number <= len(names) else None


def owner_counts(options: dict) -> list[dict]:
    """``[{name, count}]``, largest first (names shared by two users are shown
    separately only when their ids differ)."""
    stored = options.get("row_owners") if isinstance(options, dict) else None
    if not isinstance(stored, dict):
        return []
    codes = str(stored.get("codes") or "")
    names = stored.get("names") or []
    counts: Counter = Counter()
    for index in range(0, len(codes) - 1, 2):
        try:
            number = _BASE36.index(codes[index]) * 36 + _BASE36.index(codes[index + 1])
        except ValueError:
            continue
        if 0 < number <= len(names):
            counts[number - 1] += 1
    result = [{"name": names[i] or "Unknown user", "count": n} for i, n in counts.items()]
    result.sort(key=lambda item: (-item["count"], item["name"]))
    return result


# ---------------------------------------------------------------------------
# One stored row: category and plain-English text
# ---------------------------------------------------------------------------

def entry_category(entry: dict) -> str:
    result = entry.get("result")
    status = entry.get("status")
    if result == "converted":
        return CATEGORY_CONVERTED
    if result == "created":
        return CATEGORY_ADDED
    if result == "updated":
        return CATEGORY_UPDATED
    if result == "failed" or (result is None and status == ERROR):
        return CATEGORY_NEEDS_ATTENTION
    if status == EXCLUDED:
        # Rows the user asked to skip because of their errors still have real
        # problems to fix; rows the user left out by hand or by rule do not.
        if entry.get("reason") == SKIPPED_FOR_ERRORS:
            return CATEGORY_NEEDS_ATTENTION
        return CATEGORY_EXCLUDED
    return CATEGORY_SKIPPED_DUPLICATE


def is_rejected(entry: dict, include_excluded: bool = False) -> bool:
    """A row that was NOT added (and is not an update of an existing lead)."""
    category = entry_category(entry)
    if category in (CATEGORY_NEEDS_ATTENTION, CATEGORY_SKIPPED_DUPLICATE):
        return True
    return category == CATEGORY_EXCLUDED and include_excluded


def _what(duplicate: dict) -> str:
    return "email" if duplicate.get("matched_on") == MATCHED_ON_EMAIL else "phone number"


def duplicate_text(duplicate: dict) -> str:
    """``Same email as an existing lead: Priya Shah``."""
    if duplicate.get("kind") == DUPLICATE_IN_FILE:
        return f"Same {_what(duplicate)} as row {duplicate.get('first_row')} in this file"
    text = f"Same {_what(duplicate)} as an existing lead"
    if duplicate.get("name"):
        text += f": {duplicate['name']}"
    if duplicate.get("is_converted"):
        text += " (already converted, cannot be changed)"
    return text


def _duplicate_fix(duplicate: dict) -> str:
    if duplicate.get("kind") == DUPLICATE_IN_FILE:
        return (
            "Delete one of the two rows. If they are different people, correct the "
            "email or phone number, or choose 'Create anyway' when you import."
        )
    if duplicate.get("is_converted"):
        return (
            "That lead is already converted and cannot be changed. If this is a "
            "different person, correct the email or phone number and upload again."
        )
    return (
        "If this is the same person, nothing needs to be done. If it is a different "
        "person, correct the email or phone number and upload again, or choose "
        "'Update existing' or 'Create anyway' when you import."
    )


def _clean_message(message: str) -> str:
    return _ROW_PREFIX.sub("", str(message or "")).strip()


def problem_text(entry: dict) -> tuple[str, str]:
    """``(Problem, How to fix)`` of a row that was not added, in plain English."""
    category = entry_category(entry)
    note = entry.get("note")

    if category == CATEGORY_NEEDS_ATTENTION:
        problems = [p for p in (entry.get("problems") or []) if isinstance(p, dict)]
        messages, fixes = [], []
        for problem in problems:
            message = _clean_message(problem.get("message"))
            fix = str(problem.get("how_to_fix") or "").strip()
            if message and message not in messages:
                messages.append(message)
            if fix and fix not in fixes:
                fixes.append(fix)
        if not messages and note:
            messages.append(_clean_message(note))
        if not messages:
            messages.append("This row could not be added.")
        if not fixes:
            fixes.append("Check the values in this row, correct them and upload the row again.")
        return _clip(" ".join(messages)), _clip(" ".join(fixes))

    if category == CATEGORY_SKIPPED_DUPLICATE:
        duplicate = entry.get("duplicate")
        if isinstance(duplicate, dict):
            return _clip(duplicate_text(duplicate)), _clip(_duplicate_fix(duplicate))
        return (
            _clip(note or "This row was skipped."),
            "No action is needed unless you expected a change. Check that the cells "
            "you want to update are filled in.",
        )

    if category == CATEGORY_EXCLUDED:
        return (
            _clip(entry.get("reason") or "You left this row out of the import."),
            "Nothing is wrong with this row. Remove the exclusion and import again "
            "if you want it added.",
        )

    return "", ""


def result_details(entry: dict | None) -> str:
    """The 'Details' cell of the results file."""
    if entry is None:
        return ""
    category = entry_category(entry)
    if category in (CATEGORY_NEEDS_ATTENTION, CATEGORY_SKIPPED_DUPLICATE, CATEGORY_EXCLUDED):
        return _clip(" ".join(part for part in problem_text(entry) if part))

    parts = []
    duplicate = entry.get("duplicate")
    if category == CATEGORY_UPDATED:
        text = "Updated the existing lead"
        if isinstance(duplicate, dict):
            text = duplicate_text(duplicate) + ". Existing lead updated"
        parts.append(text + ".")
    elif category == CATEGORY_CONVERTED:
        parts.append("Added as a lead and converted to an account and a contact.")
    elif isinstance(duplicate, dict):
        parts.append(duplicate_text(duplicate) + ". Added anyway, as you chose.")
    for warning in entry.get("warnings") or []:
        message = warning.get("message") if isinstance(warning, dict) else None
        if message:
            parts.append(_clean_message(message))
    return _clip(" ".join(parts))


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

def _group_keys(entry: dict) -> list[tuple[str, str, str]]:
    """``[(code, title, how_to_fix)]`` the row belongs to (not-added rows only)."""
    category = entry_category(entry)
    if category == CATEGORY_NEEDS_ATTENTION:
        keys, seen = [], set()
        for problem in entry.get("problems") or []:
            if not isinstance(problem, dict):
                continue
            code = problem.get("code") or "file_error"
            if code in seen:
                continue
            seen.add(code)
            label = ERROR_CATALOG.get(code, (code.replace("_", " ").capitalize(),))[0]
            keys.append((code, label, _clip(problem.get("how_to_fix") or "", 400)))
        if keys:
            return keys
        return [(
            "not_added",
            "Could not be added",
            "Check the values in these rows, correct them and upload them again.",
        )]
    if category == CATEGORY_SKIPPED_DUPLICATE:
        duplicate = entry.get("duplicate")
        if not isinstance(duplicate, dict):
            return [(
                "no_change",
                "Nothing to update (skipped)",
                "No action is needed unless you expected a change.",
            )]
        if duplicate.get("kind") == DUPLICATE_IN_FILE:
            return [(
                "duplicate_in_file",
                "Repeated inside your file (skipped)",
                _duplicate_fix(duplicate),
            )]
        if duplicate.get("is_converted"):
            return [(
                "converted_locked",
                "Matches a converted lead (skipped)",
                _duplicate_fix(duplicate),
            )]
        return [(
            "duplicate_existing",
            "Already in your CRM (skipped)",
            _duplicate_fix(duplicate),
        )]
    if category == CATEGORY_EXCLUDED:
        return [(
            "excluded",
            "Left out by you",
            "Nothing to fix. Remove the exclusion and import again if you want these rows.",
        )]
    return []


def outcome_groups(entries: list[dict]) -> list[dict]:
    """``[{code, title, count, how_to_fix, example_rows}]``, largest first.
    ``count`` is the number of rows (a row with two kinds of problem is counted
    once in each group)."""
    groups: dict[str, dict] = {}
    for entry in entries:
        for code, title, fix in _group_keys(entry):
            group = groups.setdefault(
                code,
                {"code": code, "title": title, "count": 0, "how_to_fix": fix, "example_rows": []},
            )
            group["count"] += 1
            if len(group["example_rows"]) < MAX_EXAMPLE_ROWS:
                group["example_rows"].append(entry.get("row_number"))
    result = sorted(groups.values(), key=lambda g: (-g["count"], g["title"]))
    return result[:MAX_GROUPS]


def warning_groups(entries: list[dict]) -> list[dict]:
    """``[{code, message, count, example_rows}]`` for the warnings kept on rows."""
    groups: dict[str, dict] = {}
    for entry in entries:
        seen = set()
        for warning in entry.get("warnings") or []:
            if not isinstance(warning, dict):
                continue
            code = warning.get("code") or "warning"
            if code in seen:
                continue
            seen.add(code)
            group = groups.setdefault(
                code,
                {
                    "code": code,
                    "message": _clean_message(warning.get("message")),
                    "count": 0,
                    "example_rows": [],
                },
            )
            group["count"] += 1
            if len(group["example_rows"]) < MAX_EXAMPLE_ROWS:
                group["example_rows"].append(entry.get("row_number"))
    result = sorted(groups.values(), key=lambda g: (-g["count"], g["code"]))
    return result[:MAX_WARNING_GROUPS]


def _mapped_values(options: dict) -> dict:
    flat = []
    mapping = options.get("value_mapping")
    if isinstance(mapping, dict):
        for field_key, values in mapping.items():
            if not isinstance(values, dict):
                continue
            for raw, target in values.items():
                flat.append({
                    "field": field_key,
                    "file_value": raw,
                    "mapped_to": "(left blank)" if target == BLANK_VALUE else target,
                })
    return {
        "count": len(flat),
        "values": flat[:MAX_MAPPED_VALUES],
        "unknown_values_left_blank": bool(options.get("unknown_values_as_blank")),
    }


def _owner_assignment(options: dict):
    check = options.get("last_check")
    summary = check.get("summary") if isinstance(check, dict) else None
    owners = summary.get("owners") if isinstance(summary, dict) else None
    return to_jsonable(owners) if owners else None


def _converted_block(options: dict) -> dict:
    stored = options.get("converted") if isinstance(options.get("converted"), dict) else {}
    return {
        key: len(stored.get(key) or [])
        for key in ("accounts_created", "contacts_created", "accounts_reused", "contacts_reused")
    }


# ---------------------------------------------------------------------------
# The summary stored on the job
# ---------------------------------------------------------------------------

def stage_of(job) -> str:
    options = _options(job)
    if job.status == "failed" or options.get("stage") == STAGE_FAILED:
        return STAGE_FAILED
    if options.get("stage") == STAGE_CANCELLED:
        return STAGE_CANCELLED
    return STAGE_FINISHED


def build_report_summary(job) -> dict:
    """Everything the report and the notification need, as plain JSON."""
    options = _options(job)
    entries = _entries(job)
    categories = Counter(entry_category(entry) for entry in entries)

    total = int(job.total_rows or 0)
    processed = int(job.processed_rows or 0)
    totals = {
        "total": total,
        "created": int(job.created_count or 0),
        "updated": int(job.updated_count or 0),
        "skipped": categories[CATEGORY_SKIPPED_DUPLICATE],
        # Rows that need the user: errors, plus rows skipped because of their errors.
        "failed": categories[CATEGORY_NEEDS_ATTENTION],
        "converted": converted_count(options),
        "excluded": categories[CATEGORY_EXCLUDED],
        "not_processed": max(0, total - processed),
    }

    attention = [e for e in entries if entry_category(e) == CATEGORY_NEEDS_ATTENTION]
    problem_dicts = [
        problem
        for entry in attention
        for problem in (entry.get("problems") or [])
        if isinstance(problem, dict) and problem.get("code")
    ]

    duplicates = {
        "action": options.get("duplicate_action") or "skip",
        "matched_on_email": 0,
        "matched_on_phone": 0,
        "in_file": 0,
    }
    for entry in entries:
        duplicate = entry.get("duplicate")
        if not isinstance(duplicate, dict):
            continue
        if duplicate.get("kind") == DUPLICATE_IN_FILE:
            duplicates["in_file"] += 1
        elif duplicate.get("kind") == DUPLICATE_EXISTING:
            if duplicate.get("matched_on") == MATCHED_ON_PHONE:
                duplicates["matched_on_phone"] += 1
            else:
                duplicates["matched_on_email"] += 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage_of(job),
        "totals": totals,
        "rejected_rows": {
            "default": totals["failed"] + totals["skipped"],
            "with_excluded": totals["failed"] + totals["skipped"] + totals["excluded"],
        },
        "outcome_groups": outcome_groups(
            [e for e in entries if entry_category(e) in (
                CATEGORY_NEEDS_ATTENTION, CATEGORY_SKIPPED_DUPLICATE, CATEGORY_EXCLUDED)]
        ),
        "error_groups": error_groups(problem_dicts)[:MAX_TOP_ERROR_GROUPS],
        "duplicates": duplicates,
        "owners": owner_counts(options),
        "owner_assignment": _owner_assignment(options),
        "converted": _converted_block(options),
        "warnings": warning_groups(entries),
        "mapped_values": _mapped_values(options),
        "duration_seconds": duration_seconds(job),
    }
    summary["one_line"] = one_line_summary(job.file_name, summary, processed)
    summary["title"] = notification_title(summary)
    return summary


# ---------------------------------------------------------------------------
# Words for the timeline and the notification
# ---------------------------------------------------------------------------

def _short_name(file_name: str) -> str:
    name = str(file_name or "your file").strip() or "your file"
    return name if len(name) <= 80 else name[:77] + "..."


def one_line_summary(file_name: str, summary: dict, processed_rows: int | None = None) -> str:
    """``Imported 1,204 leads from clients.xlsx: 1,150 added, 30 updated, 18 skipped, 6 need attention``"""
    totals = summary["totals"]
    processed = totals["total"] if processed_rows is None else int(processed_rows)
    stage = summary.get("stage")

    added = f"{totals['created']:,} added"
    if totals["converted"]:
        added += f" ({totals['converted']:,} converted)"
    parts = [added]
    if totals["updated"]:
        parts.append(f"{totals['updated']:,} updated")
    if totals["skipped"]:
        parts.append(f"{totals['skipped']:,} skipped")
    if totals["excluded"]:
        parts.append(f"{totals['excluded']:,} left out")
    if totals["failed"]:
        parts.append(f"{totals['failed']:,} need attention")
    details = ", ".join(parts)
    name = _short_name(file_name)

    if stage == STAGE_CANCELLED:
        return (
            f"Import of {name} was cancelled after {processed:,} of {totals['total']:,} "
            f"rows: {details}"
        )
    if stage == STAGE_FAILED:
        return (
            f"Import of {name} stopped after {processed:,} of {totals['total']:,} "
            f"rows: {details}"
        )
    noun = _plural(processed, "lead", "leads")
    return f"Imported {processed:,} {noun} from {name}: {details}"


def notification_title(summary: dict) -> str:
    totals = summary["totals"]
    stage = summary.get("stage")
    if stage == STAGE_FAILED:
        return "Import stopped"
    base = "Import cancelled" if stage == STAGE_CANCELLED else "Import finished"
    pieces = []
    if totals["failed"]:
        pieces.append(f"{totals['failed']:,} {_plural(totals['failed'], 'row', 'rows')} to fix")
    if totals["skipped"]:
        pieces.append(f"{totals['skipped']:,} skipped")
    return f"{base} with {' and '.join(pieces)}" if pieces else base


# ---------------------------------------------------------------------------
# The report (API shape)
# ---------------------------------------------------------------------------

_FINISHED_STATUSES = ("completed", "failed", "undone", "partly_undone")

FILES_EXPIRED_MESSAGE = (
    "The downloadable files of this import are no longer available. They are removed "
    "some time after an import finishes. The numbers and problems below are still correct."
)


def report_summary_of(job) -> dict:
    """The stored summary, or a fresh one for a job that was never finalised."""
    stored = _options(job).get("report_summary")
    if isinstance(stored, dict) and stored.get("totals"):
        return stored
    return build_report_summary(job)


def is_finished(job) -> bool:
    return job.status in _FINISHED_STATUSES and _options(job).get("stage") != "running"


def build_report(job, summary: dict, created_by_name: str | None) -> dict:
    totals = summary["totals"]
    purged = job.rows_purged_at is not None
    finished = is_finished(job)
    rejected = int((summary.get("rejected_rows") or {}).get("default", 0))
    rejected_available = finished and not purged and rejected > 0
    results_available = finished and not purged and int(job.processed_rows or 0) > 0

    files = {
        "rejected_available": rejected_available,
        "results_available": results_available,
        "rows_purged": purged,
    }
    if purged:
        files["message"] = FILES_EXPIRED_MESSAGE

    undo_report = _options(job).get("undo_report")
    eligibility = undo_eligibility(job)

    report = {
        "job": {
            "id": str(job.id),
            "file_name": job.file_name,
            "status": job.status,
            "stage": summary.get("stage"),
            "created_by_name": created_by_name,
            "started_at": _iso(job.started_at),
            "finished_at": _iso(job.finished_at),
            "duration_seconds": summary.get("duration_seconds"),
        },
        "message": summary.get("one_line"),
        "totals": totals,
        "outcome_groups": summary.get("outcome_groups", []),
        "duplicates": summary.get("duplicates", {}),
        "owners": summary.get("owners", []),
        "converted": summary.get("converted", {}),
        "warnings": summary.get("warnings", []),
        "mapped_values": summary.get("mapped_values", {}),
        "files": files,
        # The same rule the history and the undo itself use.
        "can_undo": eligibility.can_undo,
        "can_reupload": rejected_available,
    }
    if isinstance(undo_report, dict):
        report["undo_report"] = undo_report
    return report
