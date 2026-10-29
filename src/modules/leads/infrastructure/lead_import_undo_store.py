"""The database side of undoing a lead import.

``DjangoUndoStore`` is the *store* that ``lead_import_undo.run_undo`` talks to.
Every query is scoped to ONE company, and every lead query also to ONE import
job, so an id that does not belong to them is simply not found. Ids come from
the job (its leads, ``options["converted"]``, ``update_snapshots``), never from
a request.

``build_undo_services`` is the timeline and the notifications for the one
summary entry and the one notification an undo produces.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.calls.infrastructure.persistence.models.django_call_model import (
    DjangoCallModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.application.services.lead_import_undo import (
    NOT_NULL_FIELDS,
    RESTORABLE_FIELDS,
)
from src.modules.leads.infrastructure.persistence.django_lead_import_job_model import (
    LeadImportJob,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import DjangoLeadModel
from src.modules.meetings.infrastructure.persistence.django_meeting_repository import (
    DjangoMeetingRepository,
)
from src.modules.meetings.infrastructure.persistence.models.django_meeting_participant_model import (
    DjangoMeetingParticipantModel,
)
from src.modules.meetings.infrastructure.persistence.models.django_meeting_related_record_model import (
    DjangoMeetingRelatedRecordModel,
)
from src.modules.notifications.application.dto.create_notification import (
    CreateNotificationDTO,
)
from src.modules.notifications.application.use_cases.create_notification import (
    CreateNotificationUseCase,
)
from src.modules.notifications.domain.enums.notification_type import NotificationType
from src.modules.notifications.infrastructure.persistence.django_notification_repository import (
    DjangoNotificationRepository,
)
from src.modules.reminders.infrastructure.persistence.django_reminder_repository import (
    DjangoReminderRepository,
)
from src.modules.shared.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)
from src.modules.tasks.infrastructure.persistence.django_task_repository import (
    DjangoTaskRepository,
)
from src.modules.tasks.infrastructure.persistence.models.django_task_model import (
    DjangoTaskModel,
)
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import (
    DjangoTimelineRepository,
)
from src.modules.timeline.infrastructure.persistence.models import TimelineEventTarget
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)

# Timeline entries written by imports themselves never count as user activity.
_IMPORT_EVENT_PREFIX = "lead_import_"

_LEAD_LIST_COLUMNS = (
    "id", "name", "created_at", "updated_at", "is_deleted", "is_converted",
)
_RESTORE_COLUMNS = ("id", "is_deleted", "is_converted") + tuple(sorted(RESTORABLE_FIELDS))


def _uuids(values) -> list[UUID]:
    result = []
    for value in values:
        try:
            result.append(value if isinstance(value, UUID) else UUID(str(value)))
        except (TypeError, ValueError, AttributeError):
            continue
    return result


class DjangoUndoStore:

    def __init__(self, *, company_id: UUID, job_id: UUID):
        if company_id is None or job_id is None:
            raise ValueError("company_id and job_id are required.")
        self._company_id = company_id
        self._job_id = job_id

    # ------------------------------------------------------------------
    # The job
    # ------------------------------------------------------------------

    def update_snapshots(self) -> dict:
        """Only the snapshot column (the job is otherwise loaded without it)."""
        value = (
            LeadImportJob.objects.filter(company_id=self._company_id, id=self._job_id)
            .values_list("update_snapshots", flat=True)
            .first()
        )
        return value if isinstance(value, dict) else {}

    def _lock_job_light(self):
        return (
            LeadImportJob.objects.select_for_update()
            .defer("rows", "problems", "update_snapshots")
            .filter(company_id=self._company_id, id=self._job_id)
            .first()
        )

    def add_progress(self, delta: dict) -> None:
        """Add to ``options["undo"]["counts"]``. Called inside the chunk's own
        transaction, so a chunk and its counters are saved together."""
        job = self._lock_job_light()
        if job is None:
            return
        options = dict(job.options) if isinstance(job.options, dict) else {}
        state = dict(options.get("undo") or {})
        counts = dict(state.get("counts") or {})
        for key, value in delta.items():
            counts[key] = int(counts.get(key) or 0) + int(value)
        state["counts"] = counts
        options["undo"] = state
        job.options = options
        job.save(update_fields=["options"])

    def release_claim(self) -> None:
        """Let another undo start (used when an undo failed half way)."""
        job = self._lock_job_light()
        if job is None:
            return
        options = dict(job.options) if isinstance(job.options, dict) else {}
        state = dict(options.get("undo") or {})
        state["state"] = "idle"
        options["undo"] = state
        job.options = options
        job.save(update_fields=["options"])

    # ------------------------------------------------------------------
    # Leads created by the job
    # ------------------------------------------------------------------

    def job_lead_rows(self, after_id, size: int, lock: bool = False) -> list[dict]:
        """The job's leads in id order, ``size`` at a time, after ``after_id``."""
        queryset = DjangoLeadModel.objects.filter(
            company_id=self._company_id, import_job_id=self._job_id
        )
        if after_id is not None:
            queryset = queryset.filter(id__gt=after_id)
        queryset = queryset.order_by("id")
        if lock:
            queryset = queryset.select_for_update()
        return list(queryset.values(*_LEAD_LIST_COLUMNS)[:size])

    def lead_activity(self, lead_ids) -> dict:
        """``{lead_id: label}`` for leads someone added work to since the import.

        Only live work counts (a task or call that was itself deleted does not).
        Timeline entries written by imports are ignored.
        """
        ids = list(lead_ids)
        found: dict = {}
        if not ids:
            return found

        def mark(label, values):
            for value in values:
                found.setdefault(value, label)

        mark("task", DjangoTaskModel.objects.filter(
            company_id=self._company_id, lead_id__in=ids, is_deleted=False,
        ).values_list("lead_id", flat=True).distinct())
        mark("call", DjangoCallModel.objects.filter(
            company_id=self._company_id, lead_id__in=ids, is_deleted=False,
        ).values_list("lead_id", flat=True).distinct())
        mark("meeting", DjangoMeetingParticipantModel.objects.filter(
            lead_id__in=ids,
            meeting__company_id=self._company_id,
            meeting__is_deleted=False,
        ).values_list("lead_id", flat=True).distinct())
        mark("meeting", DjangoMeetingRelatedRecordModel.objects.filter(
            lead_id__in=ids,
            meeting__company_id=self._company_id,
            meeting__is_deleted=False,
        ).values_list("lead_id", flat=True).distinct())
        mark("timeline", self._timeline_entities("LEAD", ids))
        return found

    def _timeline_entities(self, entity_type: str, ids):
        return (
            TimelineEventTarget.objects.filter(
                event__company_id=self._company_id,
                entity_type=entity_type,
                entity_id__in=list(ids),
                is_deleted=False,
                event__is_deleted=False,
            )
            .exclude(event__event_type__startswith=_IMPORT_EVENT_PREFIX)
            .values_list("entity_id", flat=True)
            .distinct()
        )

    def soft_delete_leads(self, ids, now: datetime) -> int:
        # The job is part of the filter: only this import's own leads.
        return DjangoLeadModel.objects.filter(
            company_id=self._company_id,
            import_job_id=self._job_id,
            id__in=list(ids),
            is_deleted=False,
        ).update(is_deleted=True, updated_at=now)

    # ------------------------------------------------------------------
    # Contacts and accounts created by the job
    # ------------------------------------------------------------------

    def contact_rows(self, ids, lock: bool = False) -> list[dict]:
        queryset = DjangoContactModel.objects.filter(
            company_id=self._company_id, id__in=_uuids(ids)
        ).order_by("id")
        if lock:
            queryset = queryset.select_for_update()
        return list(queryset.values(
            "id", "name", "created_at", "updated_at",
            "created_by_id", "modified_by_id", "is_deleted",
        ))

    def account_rows(self, ids, lock: bool = False) -> list[dict]:
        queryset = DjangoAccountModel.objects.filter(
            company_id=self._company_id, id__in=_uuids(ids)
        ).order_by("id")
        if lock:
            queryset = queryset.select_for_update()
        return list(queryset.values(
            "id", "account_name", "created_at", "updated_at",
            "created_by_id", "modified_by_id", "is_deleted",
        ))

    def contact_blockers(self, contact_ids) -> dict:
        """``{contact_id: [what uses it]}`` for contacts other records depend on."""
        ids = list(contact_ids)
        found: dict = {}
        if not ids:
            return found

        def mark(label, values):
            for value in values:
                found.setdefault(value, []).append(label)

        mark("a task", DjangoTaskModel.objects.filter(
            company_id=self._company_id, contact_id__in=ids, is_deleted=False,
        ).values_list("contact_id", flat=True).distinct())
        mark("a call", DjangoCallModel.objects.filter(
            company_id=self._company_id, contact_id__in=ids, is_deleted=False,
        ).values_list("contact_id", flat=True).distinct())
        mark("a meeting", DjangoMeetingParticipantModel.objects.filter(
            contact_id__in=ids,
            meeting__company_id=self._company_id,
            meeting__is_deleted=False,
        ).values_list("contact_id", flat=True).distinct())
        mark("a meeting", DjangoMeetingRelatedRecordModel.objects.filter(
            contact_id__in=ids,
            meeting__company_id=self._company_id,
            meeting__is_deleted=False,
        ).values_list("contact_id", flat=True).distinct())
        mark("another contact reports to it", DjangoContactModel.objects.filter(
            company_id=self._company_id, reporting_to_id__in=ids, is_deleted=False,
        ).values_list("reporting_to_id", flat=True).distinct())
        mark("a timeline entry", self._timeline_entities("CONTACT", ids))
        return found

    def account_blockers(self, account_ids, ignoring_contact_ids) -> dict:
        """``{account_id: [what uses it]}``. Contacts removed by this same
        undo (``ignoring_contact_ids``) do not count."""
        ids = list(account_ids)
        found: dict = {}
        if not ids:
            return found
        ignored = _uuids(ignoring_contact_ids)

        def mark(label, values):
            for value in values:
                found.setdefault(value, []).append(label)

        contacts = DjangoContactModel.objects.filter(
            company_id=self._company_id, account_id__in=ids, is_deleted=False,
        )
        if ignored:
            contacts = contacts.exclude(id__in=ignored)
        mark("a contact", contacts.values_list("account_id", flat=True).distinct())
        mark("a task", DjangoTaskModel.objects.filter(
            company_id=self._company_id, account_id__in=ids, is_deleted=False,
        ).values_list("account_id", flat=True).distinct())
        mark("a call", DjangoCallModel.objects.filter(
            company_id=self._company_id, account_id__in=ids, is_deleted=False,
        ).values_list("account_id", flat=True).distinct())
        mark("a timeline entry", self._timeline_entities("ACCOUNT", ids))
        return found

    def soft_delete_contacts(self, ids, now: datetime, actor_id) -> int:
        return DjangoContactModel.objects.filter(
            company_id=self._company_id, id__in=_uuids(ids), is_deleted=False,
        ).update(is_deleted=True, updated_at=now, modified_by_id=actor_id)

    def soft_delete_accounts(self, ids, now: datetime, actor_id) -> int:
        return DjangoAccountModel.objects.filter(
            company_id=self._company_id, id__in=_uuids(ids), is_deleted=False,
        ).update(is_deleted=True, updated_at=now, modified_by_id=actor_id)

    # ------------------------------------------------------------------
    # Leads the job updated
    # ------------------------------------------------------------------

    def lead_rows_for_restore(self, ids, lock: bool = False) -> dict:
        queryset = DjangoLeadModel.objects.filter(
            company_id=self._company_id, id__in=_uuids(ids)
        ).order_by("id")
        if lock:
            queryset = queryset.select_for_update()
        return {row["id"]: row for row in queryset.values(*_RESTORE_COLUMNS)}

    def restore_lead_fields(self, changes: dict, now: datetime) -> int:
        """Write the old values back. ``changes`` is ``{lead_id: {field: old}}``
        (already checked); only whitelisted fields of live, unconverted leads of
        this company are written."""
        models = list(
            DjangoLeadModel.objects.select_for_update()
            .filter(
                company_id=self._company_id,
                id__in=list(changes),
                is_deleted=False,
                is_converted=False,
            )
            .order_by("id")
        )
        columns = {"updated_at"}
        touched = []
        for model in models:
            for name, value in changes[model.id].items():
                if name not in RESTORABLE_FIELDS:
                    continue
                if value is None and name in NOT_NULL_FIELDS:
                    continue
                if name == "owner_id" and value is not None:
                    value = UUID(str(value))
                setattr(model, name, value)
                columns.add(name)
            # bulk_update does not run auto_now, so it is set here.
            model.updated_at = now
            touched.append(model)
        if touched:
            DjangoLeadModel.objects.bulk_update(touched, sorted(columns), batch_size=500)
        return len(touched)


# ---------------------------------------------------------------------------
# Timeline and notifications
# ---------------------------------------------------------------------------

def build_undo_services(company_id: UUID) -> SimpleNamespace:
    """``record_timeline(**kwargs)``, ``notify(...)`` and ``user_name(id)``."""
    users = DjangoUserRepository(company_id=company_id)
    recorder = DefaultTimelineRecorder(DjangoTimelineRepository(company_id=company_id))
    create_notification = CreateNotificationUseCase(
        DjangoNotificationRepository(company_id=company_id),
        users,
        DjangoTaskRepository(company_id=company_id),
        DjangoMeetingRepository(company_id=company_id),
        DjangoReminderRepository(company_id=company_id),
        DjangoTransactionManager(),
    )

    def notify(*, user_id: UUID, title: str, message: str, job_id: UUID) -> None:
        create_notification.execute(
            CreateNotificationDTO(
                notification_type=NotificationType.LEAD_IMPORT_UNDONE,
                title=title,
                message=message,
                user_id=user_id,
                scheduled_for=datetime.now(timezone.utc),
                lead_import_job_id=job_id,
            )
        )

    def user_name(user_id) -> str | None:
        if user_id is None:
            return None
        user = users.get_by_id(UUID(str(user_id)))
        return getattr(user, "name", None)

    def lead_exists(lead_id) -> bool:
        return DjangoLeadModel.objects.filter(
            company_id=company_id, id=lead_id
        ).exists()

    def first_job_lead_id(job_id: UUID):
        return (
            DjangoLeadModel.objects.filter(company_id=company_id, import_job_id=job_id)
            .order_by("created_at", "id")
            .values_list("id", flat=True)
            .first()
        )

    return SimpleNamespace(
        record_timeline=recorder.record,
        notify=notify,
        user_name=user_name,
        lead_exists=lead_exists,
        first_job_lead_id=first_job_lead_id,
    )
