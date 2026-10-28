"""Runs a lead import, one batch at a time.

``process_next_batch(job_id)`` is the ONLY place batch logic lives. It knows
nothing about HTTP: it gets a job id and loads the job, the company's tenant
data and the repositories itself (through ``runtime_factory``). The "process"
endpoint calls it today; a Celery task can call it unchanged later.

One call does, inside ONE database transaction:

1. lock the job row (a call that finds it locked returns the current progress
   and does nothing);
2. take the next ``batch_size`` stored rows after ``job.processed_rows``;
3. run them through the shared pipeline (``build_context`` + ``process_rows``),
   restoring the owner rotation saved on the job;
4. write the result: insert new leads in bulk, update existing leads (old
   values saved first, for undo), hand converted rows to ``convert_outcomes``,
   and count skipped and failed rows;
5. save the new counters, the problems, the owner rotation and
   ``processed_rows`` on the job.

Because step 5 is in the same transaction as step 4, "rows were written" and
"the job moved on" can never disagree: a batch is either fully done and
counted, or not done at all. That, together with the lock, is what makes a
repeated request harmless: the second call finds ``processed_rows`` already
advanced and simply takes the NEXT batch (or, when the caller passes
``expected_processed_rows``, does nothing at all).

No timeline entry and no notification here: ``finalize_job`` (Part 11) does
that once, after the job's last batch.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Callable
from uuid import UUID

from src.modules.leads.application.services.lead_import_convert import (
    NOT_ENABLED_NOTE,
    RESULT_CONVERTED,
    ConvertRowResult,
    convert_outcomes,
)
from src.modules.leads.application.services.lead_import_finalize import finalize_job
from src.modules.leads.application.services.lead_import_pipeline import (
    CONVERT,
    DUPLICATE_CREATE,
    DUPLICATE_UPDATE,
    ERROR,
    READY,
    PipelineRepositories,
    build_context,
    process_rows,
)
from src.modules.leads.application.services.lead_import_review import (
    compact_outcome,
    to_jsonable,
)
from src.modules.leads.domain.entities.lead import Lead
from src.modules.leads.domain.entities.option_text import option_text
from src.modules.picklists.domain.entities.picklist_catalog import SYSTEM_VALUE

logger = logging.getLogger(__name__)

# Job statuses (the values of LeadImportJob.Status).
STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

# options["stage"] of a job that has been started.
STAGE_RUNNING = "running"
STAGE_FINISHED = "finished"
STAGE_CANCELLED = "cancelled"
STAGE_FAILED = "failed"
STAGE_DRAFT = "draft"

# What the frontend loop does next.
NEXT_PROCESS_AGAIN = "call_process_again"
NEXT_DONE = "done"
NEXT_FAILED = "failed"

# Row results written next to each stored problem entry.
RESULT_CREATED = "created"
RESULT_UPDATED = "updated"
RESULT_SKIPPED = "skipped"
RESULT_FAILED = "failed"

DEFAULT_BATCH_SIZE = 500
MAX_BATCH_SIZE = 5000
MAX_CONSECUTIVE_FAILURES = 3

# Lead columns an UPDATE may write from the file. Owner is handled separately,
# and only when the user chose to change owners.
_UPDATABLE_FIELDS = frozenset({
    "name", "title", "company_name", "email", "mobile_number", "phone",
    "lead_source", "lead_status", "industry", "rating", "website",
    "number_of_employees", "annual_revenue", "address", "city", "state",
    "country", "postal_code", "description",
})


class ImportJobNotFound(Exception):
    """No import with this id exists."""


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProgressResult:
    job_id: str
    status: str
    stage: str | None
    total_rows: int
    processed_rows: int
    percent: int
    created: int
    updated: int
    skipped: int
    failed: int
    converted: int
    started_at: str | None
    last_activity_at: str | None
    finished_at: str | None
    message: str
    next_action: str  # call_process_again | done | failed

    def to_dict(self) -> dict:
        return asdict(self)


def _options(job) -> dict:
    return job.options if isinstance(job.options, dict) else {}


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def is_running(job) -> bool:
    """Started and not finished: the only state a batch may be processed in."""
    return (
        job.status in (STATUS_QUEUED, STATUS_PROCESSING)
        and _options(job).get("stage") == STAGE_RUNNING
    )


def _next_action(job) -> str:
    if job.status == STATUS_FAILED:
        return NEXT_FAILED
    if is_running(job):
        return NEXT_PROCESS_AGAIN
    return NEXT_DONE


def _message(job, stage) -> str:
    total = int(job.total_rows or 0)
    processed = int(job.processed_rows or 0)

    if job.status == STATUS_FAILED:
        return job.failure_message or "The import could not be completed."
    if stage == STAGE_DRAFT:
        return "This import has not been started yet."
    if stage == STAGE_CANCELLED:
        who = _options(job).get("cancelled_by_name")
        by = f" by {who}" if who else ""
        return (
            f"The import was cancelled{by} after {processed:,} of {total:,} rows. "
            "Leads already added were kept."
        )
    if job.status == STATUS_COMPLETED:
        parts = [
            f"{job.created_count:,} added",
            f"{job.updated_count:,} updated",
            f"{job.skipped_count:,} skipped",
            f"{job.failed_count:,} not imported because of errors",
        ]
        converted = int(_options(job).get("converted_count") or 0)
        if converted:
            parts.insert(2, f"{converted:,} converted")
        return "The import is finished: " + ", ".join(parts) + "."
    if job.status in (STATUS_QUEUED, STATUS_PROCESSING):
        text = f"Importing: {processed:,} of {total:,} rows done."
        if job.failure_message:
            text = f"{job.failure_message} {text}"
        return text
    return f"This import is {job.status}."


def progress_from_job(job) -> ProgressResult:
    """The progress payload of a job. Reads counters only (a light job is fine)."""
    options = _options(job)
    stage = options.get("stage")
    total = int(job.total_rows or 0)
    processed = int(job.processed_rows or 0)
    if total > 0:
        percent = min(100, int(processed * 100 / total))
    else:
        percent = 100 if job.status == STATUS_COMPLETED else 0
    return ProgressResult(
        job_id=str(job.id),
        status=job.status,
        stage=stage,
        total_rows=total,
        processed_rows=processed,
        percent=percent,
        created=int(job.created_count or 0),
        updated=int(job.updated_count or 0),
        skipped=int(job.skipped_count or 0),
        failed=int(job.failed_count or 0),
        converted=int(options.get("converted_count") or 0),
        started_at=_iso(job.started_at),
        last_activity_at=_iso(job.last_activity_at),
        finished_at=_iso(job.finished_at),
        message=_message(job, stage),
        next_action=_next_action(job),
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def resolve_batch_size(batch_size=None) -> int:
    """The given size, else ``settings.LEAD_IMPORT_BATCH_SIZE``, else 500."""
    candidate = batch_size
    if candidate is None:
        candidate = DEFAULT_BATCH_SIZE
        try:
            from django.conf import settings

            candidate = getattr(settings, "LEAD_IMPORT_BATCH_SIZE", DEFAULT_BATCH_SIZE)
        except Exception:  # noqa: BLE001 - Django not configured (scripts)
            pass
    try:
        size = int(candidate)
    except (TypeError, ValueError):
        size = DEFAULT_BATCH_SIZE
    return max(1, min(size, MAX_BATCH_SIZE))


def default_runtime_factory(job_id: UUID):
    """``job_id -> runtime`` (tenant context + repositories).

    Imported here, not at the top, so this module stays free of Django models.
    A view and a Celery task both use it; tests pass their own.
    """
    from src.modules.leads.infrastructure.lead_import_runtime import build_import_runtime

    return build_import_runtime(job_id)


# ---------------------------------------------------------------------------
# The one entry point
# ---------------------------------------------------------------------------

@dataclass
class _BatchResult:
    progress: ProgressResult
    finished_job: object | None = None  # set when this call ended the job


def process_next_batch(
    job_id,
    batch_size: int | None = None,
    *,
    expected_processed_rows: int | None = None,
    runtime_factory: Callable[[UUID], object] | None = None,
) -> ProgressResult:
    """Process the next batch of a started import and return its progress.

    Safe to call at any time, any number of times, from any process:

    * the job is locked for the whole batch; a call that finds it locked, or
      finds the job not started / already finished, returns the current
      progress unchanged;
    * ``expected_processed_rows`` (optional) is the ``processed_rows`` the
      caller last saw. When the job has moved on since, the call is a repeat of
      a batch that is already done and does nothing.

    An unexpected error rolls the batch back completely, is counted on the
    job, and after ``MAX_CONSECUTIVE_FAILURES`` in a row the job is marked
    failed. Raises ``ImportJobNotFound`` when there is no such job.
    """
    job_uuid = UUID(str(job_id))
    runtime = (runtime_factory or default_runtime_factory)(job_uuid)
    size = resolve_batch_size(batch_size)

    try:
        outcome = runtime.transaction_manager.execute(
            lambda: _run_batch(job_uuid, size, expected_processed_rows, runtime)
        )
    except ImportJobNotFound:
        raise
    except Exception:  # noqa: BLE001 - the batch is rolled back, then counted
        logger.exception("Lead import %s: a batch failed and was rolled back.", job_uuid)
        outcome = _handle_failure(job_uuid, runtime)

    if outcome.finished_job is not None:
        _run_finalize(outcome.finished_job, runtime)
    return outcome.progress


def finish_hook(job, runtime) -> None:
    """Runs ``finalize_job`` after the finishing transaction has committed.
    Its errors are logged and never change the import's result."""
    _run_finalize(job, runtime)


def _run_finalize(job, runtime) -> None:
    try:
        finalize_job(job, runtime)
    except Exception:  # noqa: BLE001 - the import itself is already saved
        logger.exception("Lead import %s: finalize_job failed.", getattr(job, "id", "?"))


# ---------------------------------------------------------------------------
# One batch (runs inside the transaction)
# ---------------------------------------------------------------------------

def _run_batch(job_id: UUID, size: int, expected_processed_rows, runtime) -> _BatchResult:
    repository = runtime.job_repository

    job = repository.lock_for_processing(job_id, skip_locked=True)
    if job is None:
        # Either another call is working on it right now, or there is no such job.
        current = repository.get_for_company(job_id, light=True)
        if current is None:
            raise ImportJobNotFound(f"Lead import {job_id} was not found.")
        return _BatchResult(progress_from_job(current))

    if not is_running(job):
        return _BatchResult(progress_from_job(job))

    start = int(job.processed_rows or 0)
    if expected_processed_rows is not None and int(expected_processed_rows) != start:
        return _BatchResult(progress_from_job(job))

    rows = job.rows
    if rows is None:
        return _fail(
            job,
            repository,
            "The rows of this import are no longer stored, so it cannot continue. "
            "Upload the file again to start a new import.",
        )

    batch_rows = rows[start:start + size]
    now = datetime.now(timezone.utc)
    options = dict(_options(job))

    fields: dict = {"status": STATUS_PROCESSING}
    if job.started_at is None:
        fields["started_at"] = now

    counts = {RESULT_CREATED: 0, RESULT_UPDATED: 0, RESULT_SKIPPED: 0,
              RESULT_FAILED: 0, RESULT_CONVERTED: 0}

    if batch_rows:
        context = build_context(
            SimpleNamespace(
                headers=job.headers,
                mapping=job.mapping,
                options=job.options,  # carries round_robin_cursor
                rows=rows,  # the whole file: in-file duplicates look across batches
            ),
            runtime.tenant_context,
            PipelineRepositories(
                lead_repository=runtime.lead_repository,
                user_repository=runtime.user_repository,
                picklist_repository=runtime.picklist_repository,
            ),
        )
        outcomes = process_rows(batch_rows, context)
        applied = _apply_outcomes(job, outcomes, context, runtime)
        counts = applied.counts

        options["round_robin_cursor"] = context.owner_cursor
        if applied.entries:
            fields["problems"] = list(job.problems or []) + applied.entries
        if applied.snapshots_changed:
            fields["update_snapshots"] = applied.snapshots

    processed = start + len(batch_rows)
    finished = processed >= len(rows)

    options.pop("consecutive_failures", None)
    options["converted_count"] = int(options.get("converted_count") or 0) + counts[RESULT_CONVERTED]
    fields.update({
        "processed_rows": processed,
        "created_count": int(job.created_count or 0) + counts[RESULT_CREATED],
        "updated_count": int(job.updated_count or 0) + counts[RESULT_UPDATED],
        "skipped_count": int(job.skipped_count or 0) + counts[RESULT_SKIPPED],
        "failed_count": int(job.failed_count or 0) + counts[RESULT_FAILED],
        "failure_message": "",
    })
    if finished:
        options["stage"] = STAGE_FINISHED
        fields["status"] = STATUS_COMPLETED
        fields["finished_at"] = now
    fields["options"] = options

    repository.save_progress(job, fields)
    return _BatchResult(progress_from_job(job), job if finished else None)


@dataclass
class _Applied:
    counts: dict
    entries: list
    snapshots: dict
    snapshots_changed: bool


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _same(old, new) -> bool:
    if _blank(old) and _blank(new):
        return True
    return old == new


def _picklist(value) -> str:
    value = option_text(value)
    return value if not _blank(value) else SYSTEM_VALUE


def _build_lead(outcome) -> Lead | None:
    """A new lead set up exactly as ``CreateLeadUseCase`` does it (dropdowns
    default to "None"); ``None`` when the row has no owner."""
    if not outcome.owner_id:
        return None
    data = outcome.payload or {}
    return Lead.create(
        name=data.get("name"),
        title=data.get("title"),
        company_name=data.get("company_name"),
        email=data.get("email"),
        mobile_number=data.get("mobile_number"),
        phone=data.get("phone"),
        lead_source=_picklist(data.get("lead_source")),
        lead_status=_picklist(data.get("lead_status")),
        industry=_picklist(data.get("industry")),
        rating=_picklist(data.get("rating")),
        website=data.get("website"),
        number_of_employees=data.get("number_of_employees"),
        annual_revenue=data.get("annual_revenue"),
        owner_id=UUID(str(outcome.owner_id)),
        address=data.get("address"),
        city=data.get("city"),
        state=data.get("state"),
        country=data.get("country"),
        postal_code=data.get("postal_code"),
        description=data.get("description"),
    )


def _apply_outcomes(job, outcomes, context, runtime) -> _Applied:
    lead_repository = runtime.lead_repository
    results: dict[int, tuple[str, str | None]] = {}

    to_create, to_update, to_convert = [], [], []
    for outcome in outcomes:
        if outcome.status in (READY, DUPLICATE_CREATE):
            to_create.append(outcome)
        elif outcome.status == DUPLICATE_UPDATE:
            to_update.append(outcome)
        elif outcome.status == CONVERT:
            to_convert.append(outcome)
        elif outcome.status == ERROR:
            results[outcome.row_number] = (RESULT_FAILED, None)
        else:  # duplicate skipped, excluded
            results[outcome.row_number] = (RESULT_SKIPPED, None)

    # New leads, in one bulk insert.
    new_leads = []
    for outcome in to_create:
        lead = _build_lead(outcome)
        if lead is None:
            results[outcome.row_number] = (
                RESULT_FAILED, "No owner could be assigned to this row.",
            )
            continue
        new_leads.append(lead)
        results[outcome.row_number] = (RESULT_CREATED, None)
    lead_repository.bulk_create_for_import(new_leads, job.id)

    # Existing leads: old values are saved before anything is changed.
    snapshots = dict(job.update_snapshots or {})
    snapshots_before = sum(len(v) for v in snapshots.values())
    changes: dict[UUID, dict] = {}
    if to_update:
        wanted_ids = {
            UUID(str(o.matched_lead_id)) for o in to_update if o.matched_lead_id
        }
        existing = lead_repository.get_many_for_update(wanted_ids)
        for outcome in to_update:
            lead_id = UUID(str(outcome.matched_lead_id)) if outcome.matched_lead_id else None
            lead = existing.get(lead_id)
            if lead is None or lead.is_converted:
                results[outcome.row_number] = (
                    RESULT_SKIPPED,
                    "The existing lead was deleted or converted after the check, "
                    "so it was not updated.",
                )
                continue

            # Empty cells never wipe data; owner only when the user asked for it.
            wanted = {
                key: value
                for key, value in (outcome.payload or {}).items()
                if key in _UPDATABLE_FIELDS and not _blank(value)
            }
            if outcome.owner_id and context.plan.change_owner_on_update:
                wanted["owner_id"] = UUID(str(outcome.owner_id))

            changed = {}
            for key, value in wanted.items():
                old = getattr(lead, key)
                if _same(old, value):
                    continue
                changed[key] = value
                # The first old value wins, even across batches.
                snapshots.setdefault(str(lead_id), {}).setdefault(key, to_jsonable(old))
                setattr(lead, key, value)  # later rows compare with the new state

            if not changed:
                results[outcome.row_number] = (
                    RESULT_SKIPPED,
                    "The existing lead already has these values, so nothing was changed.",
                )
                continue
            changes.setdefault(lead_id, {}).update(changed)
            results[outcome.row_number] = (RESULT_UPDATED, None)
        lead_repository.bulk_update_fields(changes)

    # Converted rows (Part 10).
    if to_convert:
        converted = convert_outcomes(
            job, to_convert, tenant_context=runtime.tenant_context, runtime=runtime
        )
        for outcome in to_convert:
            row = converted.get(outcome.row_number) or ConvertRowResult(
                RESULT_SKIPPED, NOT_ENABLED_NOTE
            )
            results[outcome.row_number] = (row.result, row.note)

    counts = {RESULT_CREATED: 0, RESULT_UPDATED: 0, RESULT_SKIPPED: 0,
              RESULT_FAILED: 0, RESULT_CONVERTED: 0}
    for result, _note in results.values():
        counts[result] = counts.get(result, 0) + 1

    # Everything that is not a plainly created lead is kept for the report.
    owner_names = {str(owner.id): owner.name for owner in context.eligible_owners}
    entries = []
    for outcome in outcomes:
        result, note = results[outcome.row_number]
        if outcome.status == READY and result == RESULT_CREATED:
            continue
        entry = compact_outcome(outcome, owner_names)
        entry["result"] = result
        if note:
            entry["note"] = note
        entries.append(entry)

    snapshots_changed = sum(len(v) for v in snapshots.values()) != snapshots_before
    return _Applied(counts, entries, snapshots, snapshots_changed)


# ---------------------------------------------------------------------------
# Failures
# ---------------------------------------------------------------------------

def _fail(job, repository, message: str, options: dict | None = None) -> _BatchResult:
    """Mark the job failed (terminal). Leads already added are kept."""
    options = dict(options if options is not None else _options(job))
    options["stage"] = STAGE_FAILED
    repository.save_progress(
        job,
        {
            "status": STATUS_FAILED,
            "finished_at": datetime.now(timezone.utc),
            "failure_message": message,
            "options": options,
        },
    )
    return _BatchResult(progress_from_job(job), job)


def _handle_failure(job_id: UUID, runtime) -> _BatchResult:
    """After a rolled-back batch: count it, in its own small transaction."""
    try:
        return runtime.transaction_manager.execute(
            lambda: _record_failure(job_id, runtime)
        )
    except ImportJobNotFound:
        raise
    except Exception:  # noqa: BLE001 - never hide the original problem further
        logger.exception("Lead import %s: could not record the failure.", job_id)
        current = runtime.job_repository.get_for_company(job_id, light=True)
        if current is None:
            raise ImportJobNotFound(f"Lead import {job_id} was not found.")
        return _BatchResult(progress_from_job(current))


def _record_failure(job_id: UUID, runtime) -> _BatchResult:
    repository = runtime.job_repository
    job = repository.lock_for_processing(job_id)
    if job is None:
        raise ImportJobNotFound(f"Lead import {job_id} was not found.")
    if not is_running(job):
        return _BatchResult(progress_from_job(job))

    options = dict(_options(job))
    failures = int(options.get("consecutive_failures") or 0) + 1
    options["consecutive_failures"] = failures

    if failures >= MAX_CONSECUTIVE_FAILURES:
        return _fail(
            job,
            repository,
            f"The import stopped because the next rows could not be processed "
            f"({failures} attempts in a row). The {int(job.created_count or 0):,} "
            "leads already added were kept and can be undone from the import "
            "history. Please try again later.",
            options,
        )

    repository.save_progress(
        job,
        {
            "status": STATUS_PROCESSING,
            "options": options,
            "failure_message": (
                f"A batch of rows could not be processed (attempt {failures} of "
                f"{MAX_CONSECUTIVE_FAILURES}). Nothing from it was saved; it will be "
                "tried again."
            ),
        },
    )
    return _BatchResult(progress_from_job(job))
