"""Housekeeping for lead imports, run by the cron endpoint.

One call to ``run_maintenance`` does four independent steps, in this order and
inside one time budget (so it fits a free-tier request limit):

a. resume stalled running imports (``process_next_batch`` locks, so two calls
   at once are harmless);
b. delete old drafts and their stored rows;
c. clear the stored rows of old finished imports, in small chunks (history,
   counts, problems, converted id lists and update snapshots are kept);
d. mark imports that have been stuck in "processing" for a day, after 3+
   failed batches, as failed.

Every step is wrapped: one failing never blocks the others, and a failure is
reported as a short text, never a stack trace (the details go to the log).
Steps b, c and d only touch rows that still match their condition, so a second
run at the same moment, or the same run twice, does no harm.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from src.modules.leads.application.services.lead_import_processor import (
    NEXT_PROCESS_AGAIN,
    STAGE_DRAFT,
    STAGE_FAILED,
    STAGE_RUNNING,
    STATUS_FAILED,
    STATUS_PROCESSING,
    STATUS_QUEUED,
    ImportJobNotFound,
    process_next_batch,
)
from src.modules.leads.infrastructure.persistence.django_lead_import_job_model import (
    LeadImportJob,
)
from src.modules.leads.infrastructure.persistence.django_lead_import_job_repository import (
    DjangoLeadImportJobRepository,
)

logger = logging.getLogger(__name__)

TOTAL_BUDGET_SECONDS = 20.0
# Step (a) stops early so the cheap steps (b, c, d) always have time left.
RESUME_BUDGET_SECONDS = 15.0
MAX_JOBS_RESUMED = 3
# A call that moves nothing (job locked elsewhere, or a batch that failed) is
# tried a few times, then left for the next cron run.
MAX_STUCK_CALLS = 3
DRAFT_MAX_AGE_HOURS = 24
STUCK_PROCESSING_HOURS = 24
STUCK_FAILURES = 3
CHUNK_SIZE = 50

DEFAULT_RETENTION_DAYS = 30
DEFAULT_STALL_MINUTES = 2


def _setting_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


def _step(name: str, errors: list, function, default):
    """Run one step; a failure becomes a short text and never propagates."""
    try:
        return function()
    except Exception:  # noqa: BLE001 - one step must never block the others
        logger.exception("Lead import maintenance: step '%s' failed.", name)
        errors.append(f"{name}: this step failed; see the server log.")
        return default


# ---------------------------------------------------------------------------
# a. resume stalled jobs
# ---------------------------------------------------------------------------

def _stalled_job_ids(stall_minutes: int) -> list:
    cutoff = timezone.now() - timedelta(minutes=stall_minutes)
    # Queried here (not with find_stalled) so drafts, which are also "queued",
    # can never use up the limit.
    return list(
        LeadImportJob.objects.filter(
            status__in=(STATUS_QUEUED, STATUS_PROCESSING),
            options__stage=STAGE_RUNNING,
            last_activity_at__lt=cutoff,
        )
        .order_by("last_activity_at")
        .values_list("id", flat=True)[:MAX_JOBS_RESUMED]
    )


def resume_stalled_jobs(deadline: float, stall_minutes: int, errors: list) -> list:
    resumed = []
    for job_id in _stalled_job_ids(stall_minutes):
        if time.monotonic() >= deadline:
            break
        entry = {"job_id": str(job_id), "processed_rows": None, "status": None}
        resumed.append(entry)
        try:
            stuck_calls = 0
            while time.monotonic() < deadline:
                before = entry["processed_rows"]
                progress = process_next_batch(job_id)
                entry["processed_rows"] = progress.processed_rows
                entry["status"] = progress.status
                if progress.next_action != NEXT_PROCESS_AGAIN:
                    break
                if before is not None and progress.processed_rows <= before:
                    stuck_calls += 1
                    if stuck_calls >= MAX_STUCK_CALLS:
                        break
                else:
                    stuck_calls = 0
        except ImportJobNotFound:
            entry["status"] = "not_found"
        except Exception:  # noqa: BLE001 - the next job is still resumed
            logger.exception("Lead import %s: resuming failed.", job_id)
            entry["status"] = entry["status"] or "error"
            errors.append(f"resume {job_id}: could not be resumed; see the server log.")
    return resumed


# ---------------------------------------------------------------------------
# b. old drafts
# ---------------------------------------------------------------------------

def delete_old_drafts(deadline: float) -> int:
    cutoff = timezone.now() - timedelta(hours=DRAFT_MAX_AGE_HOURS)
    deleted = 0
    while time.monotonic() < deadline:
        ids = list(
            LeadImportJob.objects.filter(
                status=STATUS_QUEUED,
                options__stage=STAGE_DRAFT,
                last_activity_at__lt=cutoff,
            ).values_list("id", flat=True)[:CHUNK_SIZE]
        )
        if not ids:
            break
        # The conditions are repeated, so a draft that was started (or touched)
        # since it was listed is not deleted, and a second run finds nothing.
        count, _ = LeadImportJob.objects.filter(
            id__in=ids,
            status=STATUS_QUEUED,
            options__stage=STAGE_DRAFT,
            last_activity_at__lt=cutoff,
        ).delete()
        deleted += count
        if count == 0:
            break
    return deleted


# ---------------------------------------------------------------------------
# c. purge stored rows
# ---------------------------------------------------------------------------

def purge_old_rows(deadline: float, retention_days: int) -> int:
    cutoff = timezone.now() - timedelta(days=retention_days)
    purged = 0
    while time.monotonic() < deadline:
        ids = list(
            LeadImportJob.objects.filter(
                status__in=DjangoLeadImportJobRepository.FINISHED_STATUSES,
                created_at__lt=cutoff,
                rows_purged_at__isnull=True,
            ).values_list("id", flat=True)[:CHUNK_SIZE]
        )
        if not ids:
            break
        # Only ``rows`` is cleared: counts, problems, converted id lists and
        # update snapshots stay, so history, reports and undo keep working.
        count = LeadImportJob.objects.filter(
            id__in=ids, rows_purged_at__isnull=True
        ).update(rows=None, rows_purged_at=timezone.now())
        purged += count
        if count == 0:
            break
    return purged


# ---------------------------------------------------------------------------
# d. jobs stuck for a day
# ---------------------------------------------------------------------------

STUCK_MESSAGE = (
    "The import was stopped because it made no progress for more than a day "
    "after several failed attempts. The leads already added were kept and can "
    "be undone from the import history. Please try the import again."
)


def mark_stuck_jobs_failed(deadline: float, errors: list) -> int:
    cutoff = timezone.now() - timedelta(hours=STUCK_PROCESSING_HOURS)
    ids = list(
        LeadImportJob.objects.filter(
            status=STATUS_PROCESSING,
            options__stage=STAGE_RUNNING,
            options__consecutive_failures__gte=STUCK_FAILURES,
            last_activity_at__lt=cutoff,
        ).values_list("id", flat=True)[:CHUNK_SIZE]
    )
    marked = 0
    for job_id in ids:
        if time.monotonic() >= deadline:
            break
        try:
            finished = _mark_failed(job_id, cutoff)
        except Exception:  # noqa: BLE001 - the other jobs are still checked
            logger.exception("Lead import %s: could not be marked failed.", job_id)
            errors.append(f"mark_failed {job_id}: failed; see the server log.")
            continue
        if finished is not None:
            marked += 1
            _notify(finished)
    return marked


def _mark_failed(job_id, cutoff):
    """Fail one job if it still matches. Returns the job, or None if it moved on."""
    with transaction.atomic():
        stored = LeadImportJob.objects.filter(id=job_id).values_list(
            "company_id", flat=True
        ).first()
        if stored is None:
            return None
        repository = DjangoLeadImportJobRepository(company_id=stored)
        job = repository.lock_for_processing(job_id, skip_locked=True)
        if job is None:
            return None
        options = dict(job.options) if isinstance(job.options, dict) else {}
        still_stuck = (
            job.status == STATUS_PROCESSING
            and options.get("stage") == STAGE_RUNNING
            and int(options.get("consecutive_failures") or 0) >= STUCK_FAILURES
            and job.last_activity_at < cutoff
        )
        if not still_stuck:
            return None
        options["stage"] = STAGE_FAILED
        repository.save_progress(
            job,
            {
                "status": STATUS_FAILED,
                "finished_at": datetime.now(dt_timezone.utc),
                "failure_message": STUCK_MESSAGE,
                "options": options,
            },
        )
        return job


def _notify(job) -> None:
    """Tell the user, like any other finished import. Never raises."""
    try:
        from src.modules.leads.application.services.lead_import_processor import (
            finish_hook,
        )
        from src.modules.leads.infrastructure.lead_import_runtime import (
            build_import_runtime,
        )

        finish_hook(job, build_import_runtime(job.id))
    except Exception:  # noqa: BLE001 - the job is already marked failed
        logger.exception("Lead import %s: failure notice could not be sent.", job.id)


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------

def run_maintenance() -> dict:
    started = time.monotonic()
    total_deadline = started + TOTAL_BUDGET_SECONDS
    resume_deadline = started + RESUME_BUDGET_SECONDS
    errors: list = []

    stall_minutes = _setting_int("LEAD_IMPORT_STALL_MINUTES", DEFAULT_STALL_MINUTES)
    retention_days = _setting_int("LEAD_IMPORT_RETENTION_DAYS", DEFAULT_RETENTION_DAYS)

    resumed = _step(
        "resume", errors,
        lambda: resume_stalled_jobs(resume_deadline, stall_minutes, errors), [],
    )
    drafts_deleted = _step(
        "drafts", errors, lambda: delete_old_drafts(total_deadline), 0
    )
    rows_purged = _step(
        "purge", errors, lambda: purge_old_rows(total_deadline, retention_days), 0
    )
    marked_failed = _step(
        "mark_failed", errors, lambda: mark_stuck_jobs_failed(total_deadline, errors), 0
    )

    return {
        "resumed": resumed,
        "drafts_deleted": drafts_deleted,
        "rows_purged": rows_purged,
        "marked_failed": marked_failed,
        "errors": errors,
        "took_ms": int((time.monotonic() - started) * 1000),
    }
