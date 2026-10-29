"""What happens once, when an import reaches its end.

``finalize_job`` is called once per job, right after the transaction that
finished it has been committed, whichever way it ended: completed, cancelled
(``options["stage"] == "cancelled"``, status still completed) or failed.

It does three things, in this order:

1. CLAIM (own short transaction): lock the job row, stop if
   ``options["finalized_at"]`` is already set, otherwise store
   ``options["report_summary"]`` and ``options["finalized_at"]``. Because the
   row is locked, two callers can never both get past this point: that is what
   makes the timeline entry and the notification happen once. (The summary is
   stored in the claim and not in the batch transaction because the claim has
   to be the very thing that decides who finalises.)
2. ONE timeline entry (``lead_import_completed``; ``lead_import_cancelled`` or
   ``lead_import_failed`` for the other endings), never one per lead.
3. ONE notification to the person who uploaded the file.

Steps 2 and 3 are independent and best effort: an error in either is logged
and never changes the import, the other step or the job's status. A failed
step is not retried (the claim is already stored), by design: a duplicate
notification would be worse than a missing one.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from src.modules.leads.application.services.lead_import_report import (
    STAGE_CANCELLED,
    STAGE_FAILED,
    build_report_summary,
)

logger = logging.getLogger(__name__)

EVENT_COMPLETED = "lead_import_completed"
EVENT_CANCELLED = "lead_import_cancelled"
EVENT_FAILED = "lead_import_failed"
_EVENTS = {STAGE_CANCELLED: EVENT_CANCELLED, STAGE_FAILED: EVENT_FAILED}

TIMELINE_MESSAGE_LIMIT = 500


def finalize_job(job, runtime=None, services=None) -> None:
    """Report an import that has ended. Safe to call any number of times.

    ``runtime`` is the import runtime (tenant context, job repository,
    transaction manager); built from the job when not given (the cancel
    endpoint passes none). ``services`` offers ``record_timeline``, ``notify``
    and ``anchor_lead_id``; the real ones are built when not given.
    """
    job_id = UUID(str(job.id))
    if runtime is None:
        from src.modules.leads.infrastructure.lead_import_runtime import (
            build_import_runtime,
        )

        runtime = build_import_runtime(job_id)

    claimed = runtime.transaction_manager.execute(lambda: _claim(job_id, runtime))
    if claimed is None:
        return
    locked, summary = claimed

    if services is None:
        from src.modules.leads.infrastructure.lead_import_finalize_services import (
            build_finalize_services,
        )

        services = build_finalize_services(runtime.tenant_context.company_id)

    _record_timeline(locked, summary, services)
    _send_notification(locked, summary, services)


def _claim(job_id: UUID, runtime):
    repository = runtime.job_repository
    locked = repository.lock_for_processing(job_id)
    if locked is None:
        return None
    options = dict(locked.options) if isinstance(locked.options, dict) else {}
    if options.get("finalized_at"):
        return None  # already done by an earlier call
    if options.get("stage") in ("running", "draft"):
        return None  # not over yet; the call that ends it will finalise

    summary = build_report_summary(locked)
    options["report_summary"] = summary
    options["finalized_at"] = datetime.now(timezone.utc).isoformat()
    repository.save_progress(locked, {"options": options})
    return locked, summary


def _record_timeline(job, summary: dict, services) -> None:
    try:
        totals = summary["totals"]
        if totals["created"] + totals["updated"] == 0:
            # Nothing changed in the CRM, so there is no lead to hang the entry on.
            logger.info(
                "Lead import %s changed no leads; no timeline entry was recorded.", job.id
            )
            return
        anchor = services.anchor_lead_id(job)
        if anchor is None:
            logger.info("Lead import %s: no lead to anchor the timeline entry on.", job.id)
            return
        services.record_timeline(
            event_type=_EVENTS.get(summary.get("stage"), EVENT_COMPLETED),
            actor_id=job.created_by_id,
            message=summary["one_line"][:TIMELINE_MESSAGE_LIMIT],
            metadata={"job_id": str(job.id), "counts": totals},
            targets=[("LEAD", anchor)],
        )
    except Exception:  # noqa: BLE001 - the import is already saved
        logger.exception("Lead import %s: the timeline entry could not be recorded.", job.id)


def _send_notification(job, summary: dict, services) -> None:
    try:
        message = summary["one_line"]
        if summary.get("stage") == STAGE_FAILED and job.failure_message:
            message = f"{message}. {job.failure_message}"
        services.notify(
            user_id=job.created_by_id,
            title=summary["title"],
            message=message,
            job_id=job.id,
        )
    except Exception:  # noqa: BLE001 - never fail the job because of a notification
        logger.exception("Lead import %s: the notification could not be sent.", job.id)
