"""UndoLeadImportUseCase: take back an import, safely, in chunks."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from src.modules.leads.application.services.lead_import_undo import (
    EVENT_UNDONE,
    STATUS_PARTLY_UNDONE,
    STATUS_UNDONE,
    TIMELINE_MESSAGE_LIMIT,
    UndoEligibility,
    UndoRun,
    build_undo_report,
    run_undo,
    undo_eligibility,
)
from src.modules.leads.application.use_cases.lead_import_common import (
    ImportRequestError,
    not_found,
)
from src.modules.leads.application.use_cases.lead_import_run_common import (
    load_started_job,
)
from src.modules.shared.application.tenant_context import TenantContext

logger = logging.getLogger(__name__)


def _refusal(eligibility: UndoEligibility) -> ImportRequestError:
    return ImportRequestError(
        eligibility.code or "undo_not_allowed",
        eligibility.reason or "This import cannot be undone.",
        eligibility.how_to_fix or "",
        status_code=eligibility.status_code,
    )


class UndoLeadImportUseCase:
    """Undo an import: remove what it added and untouched, restore what it
    updated and untouched, leave everything else alone and report it.

    The steps, each safe to repeat:

    1. CLAIM (own transaction): lock the job, check it may be undone, mark
       ``options["undo"]["state"] = "running"``. A second undo that arrives now
       is refused (409 ``undo_in_progress``); a claim older than ten minutes
       (a crashed server) is taken over.
    2. CHUNKS: ``run_undo`` goes through the leads, contacts, accounts and
       restores in chunks of 500, each chunk in its own transaction that locks
       its rows, checks them again, soft-deletes / restores them and saves its
       counters. A failure rolls back only the chunk in progress; what earlier
       chunks did stays done and is not repeated by the next attempt (removed
       records are already deleted, restored leads already hold the old values).
    3. FINISH (own transaction): ``undone`` when nothing was left alone, else
       ``partly_undone``; stores ``options["undo_report"]``, ``undone_at`` and
       ``undone_by``.
    4. ONE timeline entry and ONE notification (best effort: an error in either
       is logged and never changes the result).

    Only ids stored on the job are used, inside the job's own company. The
    request body carries nothing but ``confirm``.
    """

    def __init__(
        self,
        job_repository,
        tenant_context: TenantContext,
        transaction_manager,
        store_factory: Callable[[UUID], object],
        services_factory: Callable[[], object],
    ):
        self.job_repository = job_repository
        self.tenant_context = tenant_context
        self.transaction_manager = transaction_manager
        self.store_factory = store_factory
        self.services_factory = services_factory

    # ------------------------------------------------------------------

    def execute(self, job_id: UUID, confirm) -> dict:
        if confirm is not True:
            raise ImportRequestError(
                "confirmation_required",
                "Undoing an import needs your confirmation.",
                'Send {"confirm": true} after checking the undo preview.',
            )

        job = load_started_job(self.job_repository, job_id)  # company-scoped, light
        eligibility = undo_eligibility(job)
        if not eligibility.can_undo:
            raise _refusal(eligibility)

        user_id = self.tenant_context.user_id
        attempt = self.transaction_manager.execute(lambda: self._claim(job_id, user_id))

        store = self.store_factory(job_id)
        try:
            run = run_undo(
                job,
                store,
                dry_run=False,
                snapshots=store.update_snapshots(),
                transaction_manager=self.transaction_manager,
                actor_id=user_id,
            )
            if run.actions == 0 and run.left_alone_total > 0:
                store.release_claim()
                raise ImportRequestError(
                    "nothing_to_undo",
                    "Nothing could be undone: every record from this import was changed "
                    "or used since it ran, so all of them were left alone.",
                    "Open the undo preview to see each record and the reason.",
                )
            finished = self.transaction_manager.execute(
                lambda: self._finish(job_id, run, attempt, user_id)
            )
        except ImportRequestError:
            raise
        except Exception:
            logger.exception("Lead import %s: the undo failed part-way.", job_id)
            try:
                store.release_claim()
            except Exception:  # noqa: BLE001 - the claim also times out by itself
                logger.exception("Lead import %s: could not release the undo claim.", job_id)
            raise

        report, status, locked, first_report = finished
        self._announce(locked, run, report, first_report)
        return {
            "job_id": str(job_id),
            "status": status,
            "message": report["message"],
            "undo_report": report,
            "can_undo": undo_eligibility(locked).can_undo,
        }

    # ------------------------------------------------------------------

    def _claim(self, job_id: UUID, user_id) -> int:
        locked = self.job_repository.lock_for_processing(job_id)
        if locked is None:
            raise not_found()
        # Checked again under the lock: two requests cannot both get past here.
        eligibility = undo_eligibility(locked)
        if not eligibility.can_undo:
            raise _refusal(eligibility)

        options = dict(locked.options) if isinstance(locked.options, dict) else {}
        state = dict(options.get("undo") or {})
        attempt = int(state.get("attempts") or 0) + 1
        state.update({
            "state": "running",
            "run_started_at": datetime.now(timezone.utc).isoformat(),
            "run_by": str(user_id),
            "attempts": attempt,
        })
        options["undo"] = state
        self.job_repository.save_progress(locked, {"options": options})
        return attempt

    def _finish(self, job_id: UUID, run: UndoRun, attempt: int, user_id):
        locked = self.job_repository.lock_for_processing(job_id)
        if locked is None:
            raise not_found()
        options = dict(locked.options) if isinstance(locked.options, dict) else {}
        state = dict(options.get("undo") or {})
        counts = dict(state.get("counts") or {})
        first_report = not isinstance(options.get("undo_report"), dict)
        if first_report:
            # Records the users deleted themselves before the undo. Records an
            # earlier, interrupted attempt of this undo already removed also
            # look "already deleted" now, so they are taken off.
            removed_now = run.removed_leads + run.removed_contacts + run.removed_accounts
            removed_all = (
                int(counts.get("leads_removed") or 0)
                + int(counts.get("contacts_removed") or 0)
                + int(counts.get("accounts_removed") or 0)
            )
            earlier = max(0, removed_all - removed_now)
            counts["already_deleted"] = max(0, run.already_deleted - earlier)
        state["counts"] = counts
        state["state"] = "idle"
        options["undo"] = state

        status = STATUS_PARTLY_UNDONE if run.left_alone_total > 0 else STATUS_UNDONE
        now = datetime.now(timezone.utc)
        services = self.services_factory()
        report = build_undo_report(
            locked,
            run,
            counts,
            attempt=attempt,
            undone_at=now,
            undone_by=user_id,
            undone_by_name=self._name(services, user_id),
            status=status,
        )
        options["undo_report"] = report
        self.job_repository.save_progress(
            locked,
            {
                "status": status,
                "options": options,
                "undone_at": now,
                "undone_by_id": user_id,
            },
        )
        return report, status, locked, first_report

    @staticmethod
    def _name(services, user_id) -> str | None:
        try:
            return services.user_name(user_id)
        except Exception:  # noqa: BLE001 - a name is nice to have
            return None

    # ------------------------------------------------------------------

    def _announce(self, job, run: UndoRun, report: dict, first_report: bool) -> None:
        try:
            services = self.services_factory()
        except Exception:  # noqa: BLE001 - the undo itself is already saved
            logger.exception("Lead import %s: the undo notices could not be set up.", job.id)
            return
        self._record_timeline(services, job, run, report)
        if first_report:
            self._notify(services, job, report)

    def _record_timeline(self, services, job, run: UndoRun, report: dict) -> None:
        try:
            anchor = run.anchor_lead_id() or services.first_job_lead_id(job.id)
            if anchor is None:
                logger.info("Lead import %s: no lead to hang the undo entry on.", job.id)
                return
            services.record_timeline(
                event_type=EVENT_UNDONE,
                actor_id=self.tenant_context.user_id,
                message=report["message"][:TIMELINE_MESSAGE_LIMIT],
                metadata={
                    "job_id": str(job.id),
                    "counts": report["counts"],
                    "status": report["status"],
                },
                targets=[("LEAD", UUID(str(anchor)))],
            )
        except Exception:  # noqa: BLE001 - never fail the undo because of the timeline
            logger.exception("Lead import %s: the undo timeline entry failed.", job.id)

    def _notify(self, services, job, report: dict) -> None:
        # The person who ran the import, and the person who undid it if that
        # is somebody else. (The database allows one such notification per
        # import and user, so only the first finished undo sends them.)
        recipients = [job.created_by_id]
        if str(self.tenant_context.user_id) != str(job.created_by_id):
            recipients.append(self.tenant_context.user_id)

        title = (
            "Import undone"
            if report["status"] == STATUS_UNDONE
            else "Import partly undone"
        )
        who = report.get("undone_by_name")
        message = f"{report['message']}" + (f" (by {who})." if who else ".")
        for user_id in recipients:
            try:
                services.notify(
                    user_id=user_id, title=title, message=message, job_id=job.id
                )
            except Exception:  # noqa: BLE001 - never fail the undo because of a notification
                logger.exception(
                    "Lead import %s: the undo notification could not be sent.", job.id
                )

