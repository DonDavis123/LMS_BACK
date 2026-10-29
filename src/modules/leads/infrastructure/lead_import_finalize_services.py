"""The outside world ``finalize_job`` talks to: the timeline, the notifications
module and the lead table, all scoped to one company.

Kept apart from ``lead_import_finalize`` so that module stays free of Django
and a test can pass its own fakes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from src.modules.leads.infrastructure.persistence.django_lead_model import DjangoLeadModel
from src.modules.meetings.infrastructure.persistence.django_meeting_repository import (
    DjangoMeetingRepository,
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
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import (
    DjangoTimelineRepository,
)
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)


def build_finalize_services(company_id: UUID) -> SimpleNamespace:
    """``record_timeline(**kwargs)``, ``notify(...)`` and ``anchor_lead_id(job)``
    of one company."""
    recorder = DefaultTimelineRecorder(DjangoTimelineRepository(company_id=company_id))
    create_notification = CreateNotificationUseCase(
        DjangoNotificationRepository(company_id=company_id),
        DjangoUserRepository(company_id=company_id),
        DjangoTaskRepository(company_id=company_id),
        DjangoMeetingRepository(company_id=company_id),
        DjangoReminderRepository(company_id=company_id),
        DjangoTransactionManager(),
    )

    def notify(*, user_id: UUID, title: str, message: str, job_id: UUID) -> None:
        create_notification.execute(
            CreateNotificationDTO(
                notification_type=NotificationType.LEAD_IMPORT_FINISHED,
                title=title,
                message=message,
                user_id=user_id,
                scheduled_for=datetime.now(timezone.utc),
                lead_import_job_id=job_id,
            )
        )

    def anchor_lead_id(job) -> UUID | None:
        """A lead the one summary timeline entry can hang on: the first lead the
        import added, else the first one it updated. ``None`` when it did
        neither (the entry is then not recorded)."""
        leads = DjangoLeadModel.objects.filter(company_id=company_id, is_deleted=False)
        first = (
            leads.filter(import_job_id=job.id)
            .order_by("created_at", "id")
            .values_list("id", flat=True)
            .first()
        )
        if first is not None:
            return first
        for key in (job.update_snapshots or {}):
            try:
                candidate = UUID(str(key))
            except ValueError:
                continue
            if leads.filter(id=candidate).exists():
                return candidate
        return None

    return SimpleNamespace(
        record_timeline=recorder.record,
        notify=notify,
        anchor_lead_id=anchor_lead_id,
    )
