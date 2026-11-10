from datetime import datetime
from uuid import UUID

from django.db.models import Q

from src.modules.calendar.application.dto.calendar_event import CalendarEventDTO
from src.modules.calendar.application.interfaces.calendar_repository import (
    CalendarRepository,
)
from src.modules.calls.infrastructure.persistence.models.django_call_model import (
    DjangoCallModel,
)
from src.modules.meetings.infrastructure.persistence.models.django_meeting_model import (
    DjangoMeetingModel,
)
from src.modules.reminders.infrastructure.persistence.models.django_reminder_model import (
    DjangoReminderModel,
)
from src.modules.tasks.infrastructure.persistence.models.django_task_model import (
    DjangoTaskModel,
)

# Safety cap per item type so a huge range can never return an unbounded list.
MAX_PER_TYPE = 500


def _related(model):
    """(type, id, name) of the lead / contact / account an item belongs to."""
    if getattr(model, "lead_id", None):
        return "LEAD", model.lead_id, model.lead.name
    if getattr(model, "contact_id", None):
        return "CONTACT", model.contact_id, model.contact.name
    if getattr(model, "account_id", None):
        return "ACCOUNT", model.account_id, model.account.account_name
    return None, None, None


class DjangoCalendarRepository(CalendarRepository):

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def get_tasks(self, *, start: datetime, end: datetime, user_id: UUID | None):
        # Tasks only have a due *date*, so they are shown as all-day items. The
        # range's own wall dates are used so the caller's time zone is honoured.
        queryset = (
            DjangoTaskModel.objects.filter(
                company_id=self._company_id,
                is_deleted=False,
                due_date__isnull=False,
                due_date__gte=start.date(),
                due_date__lt=end.date(),
            )
            .select_related("owner", "lead", "contact", "account")
            .order_by("due_date", "id")
        )

        if user_id is not None:
            queryset = queryset.filter(Q(owner_id=user_id) | Q(assigned_to_id=user_id))

        events = []
        for task in queryset[:MAX_PER_TYPE]:
            record_type, record_id, record_name = _related(task)
            events.append(
                CalendarEventDTO(
                    id=task.id,
                    type="TASK",
                    title=task.subject,
                    start=task.due_date,
                    end=None,
                    all_day=True,
                    status=task.status,
                    owner_id=task.owner_id,
                    owner_name=task.owner.name if task.owner else None,
                    related_record_type=record_type,
                    related_record_id=record_id,
                    related_record_name=record_name,
                    reminder_at=task.reminder_at,
                )
            )
        return events

    def get_meetings(self, *, start: datetime, end: datetime, user_id: UUID | None):
        # A meeting is in range when it overlaps it.
        queryset = (
            DjangoMeetingModel.objects.filter(
                company_id=self._company_id,
                is_deleted=False,
                start_at__lt=end,
                end_at__gte=start,
            )
            .select_related("host")
            .order_by("start_at", "id")
        )

        if user_id is not None:
            queryset = queryset.filter(
                Q(host_id=user_id) | Q(participants__user_id=user_id)
            ).distinct()

        return [
            CalendarEventDTO(
                id=meeting.id,
                type="MEETING",
                title=meeting.title,
                start=meeting.start_at,
                end=meeting.end_at,
                all_day=meeting.is_all_day,
                status=None,
                owner_id=meeting.host_id,
                owner_name=meeting.host.name if meeting.host else None,
                reminder_at=meeting.reminder_at,
            )
            for meeting in queryset[:MAX_PER_TYPE]
        ]

    def get_calls(self, *, start: datetime, end: datetime, user_id: UUID | None):
        queryset = (
            DjangoCallModel.objects.filter(
                company_id=self._company_id,
                is_deleted=False,
                call_start_time__gte=start,
                call_start_time__lt=end,
            )
            .select_related("owner", "lead", "contact", "account")
            .order_by("call_start_time", "id")
        )

        if user_id is not None:
            queryset = queryset.filter(owner_id=user_id)

        events = []
        for call in queryset[:MAX_PER_TYPE]:
            record_type, record_id, record_name = _related(call)
            title = f"{call.call_type} call"
            if record_name:
                title += f" – {record_name}"

            events.append(
                CalendarEventDTO(
                    id=call.id,
                    type="CALL",
                    title=title,
                    start=call.call_start_time,
                    end=None,
                    all_day=False,
                    status=call.status,
                    owner_id=call.owner_id,
                    owner_name=call.owner.name if call.owner else None,
                    related_record_type=record_type,
                    related_record_id=record_id,
                    related_record_name=record_name,
                )
            )
        return events

    def get_reminders(self, *, start: datetime, end: datetime, user_id: UUID | None):
        # Reminders attached to a task or meeting already show on that item.
        queryset = (
            DjangoReminderModel.objects.filter(
                company_id=self._company_id,
                task__isnull=True,
                meeting__isnull=True,
                remind_at__gte=start,
                remind_at__lt=end,
            )
            .select_related("user")
            .order_by("remind_at", "id")
        )

        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)

        return [
            CalendarEventDTO(
                id=reminder.id,
                type="REMINDER",
                title=reminder.subject,
                start=reminder.remind_at,
                end=None,
                all_day=False,
                status="Enabled" if reminder.is_enabled else "Disabled",
                owner_id=reminder.user_id,
                owner_name=reminder.user.name if reminder.user else None,
            )
            for reminder in queryset[:MAX_PER_TYPE]
        ]
