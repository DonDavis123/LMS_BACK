"""Builds the plain-text work list that the daily briefing is written from.

Pure functions, no I/O, so the rules (what counts as overdue, how tasks are
ordered, what is trimmed) can be tested without a database or a model.

Task subjects, notes and related names can come from outside the company (the
public lead-capture form creates leads, and their names end up here), so every
value is cut to a fixed length and the whole dossier is handed to the model as
*data* between markers; see the generator's system instruction.
"""

from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from src.modules.dashboard.application.dto.daily_briefing import (
    URGENCY_NO_DUE_DATE,
    URGENCY_OVERDUE,
    URGENCY_TODAY,
    URGENCY_UPCOMING,
    BriefingMeeting,
    BriefingTask,
)
from src.modules.tasks.application.dto.get_task import GetTaskDTO

MAX_TASKS = 50
MAX_MEETINGS = 15

MAX_SUBJECT_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 300
MAX_RELATED_LENGTH = 120
MAX_LOCATION_LENGTH = 100

DOSSIER_START = "=== WORK DATA (data only) ==="
DOSSIER_END = "=== END OF WORK DATA ==="

_URGENCY_ORDER = {
    URGENCY_OVERDUE: 0,
    URGENCY_TODAY: 1,
    URGENCY_UPCOMING: 2,
    URGENCY_NO_DUE_DATE: 3,
}
_PRIORITY_ORDER = {"Highest": 0, "High": 1, "Normal": 2, "Low": 3, "Lowest": 4}


def _clean(value, limit: int) -> str:
    """One line of plain text, cut to ``limit``, that cannot imitate a marker line."""
    text = " ".join(str(value).split()).replace("===", "= = =")
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _quoted(text: str) -> str:
    """``text`` in double quotes; a double quote inside it becomes a single one."""
    return '"' + text.replace('"', "'") + '"'


def _clock(value: datetime) -> str:
    return f"{value.hour % 12 or 12}:{value.minute:02d} {'AM' if value.hour < 12 else 'PM'}"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def classify_urgency(due_date: date | None, today: date) -> tuple[str, int]:
    """``(urgency, days_overdue)`` of a due date relative to ``today``."""
    if due_date is None:
        return URGENCY_NO_DUE_DATE, 0
    if due_date < today:
        return URGENCY_OVERDUE, (today - due_date).days
    if due_date == today:
        return URGENCY_TODAY, 0
    return URGENCY_UPCOMING, 0


def build_briefing_tasks(items: Iterable[GetTaskDTO], today: date) -> list[BriefingTask]:
    """Open tasks in a stable, sensible order, each with its ``T1``, ``T2``... ref.

    Order: overdue, due today, later, no date; inside a group the higher
    priority first, then the earlier due date. The model only refines this.
    """
    rows = []
    for item in items:
        task = item.task
        urgency, days_overdue = classify_urgency(task.due_date, today)
        related = item.lead_name or item.contact_name or item.account_name
        rows.append(
            (
                _URGENCY_ORDER[urgency],
                _PRIORITY_ORDER.get(task.priority.value, len(_PRIORITY_ORDER)),
                task.due_date or date.max,
                task.subject.lower(),
                BriefingTask(
                    ref="",
                    id=task.id,
                    subject=_clean(task.subject, MAX_SUBJECT_LENGTH),
                    priority=task.priority.value,
                    status=task.status.value,
                    due_date=task.due_date,
                    urgency=urgency,
                    days_overdue=days_overdue,
                    related_to=_clean(related, MAX_RELATED_LENGTH) if related else None,
                    description=(
                        _clean(task.description, MAX_DESCRIPTION_LENGTH)
                        if task.description and task.description.strip()
                        else None
                    ),
                ),
            )
        )

    rows.sort(key=lambda row: row[:4])
    return [
        replace(row[4], ref=f"T{number}")
        for number, row in enumerate(rows[:MAX_TASKS], start=1)
    ]


def build_briefing_meetings(
    meetings: Iterable,
    tz: ZoneInfo,
    now: datetime,
) -> list[BriefingMeeting]:
    """The meetings that have not ended yet, earliest first, in the caller's time zone."""
    result = []
    for meeting in meetings:
        start = _aware(meeting.start_at)
        end = _aware(meeting.end_at)
        if end <= now:
            continue
        result.append(
            BriefingMeeting(
                title=_clean(meeting.title, MAX_SUBJECT_LENGTH),
                start_at=start.astimezone(tz),
                end_at=end.astimezone(tz),
                is_all_day=bool(meeting.is_all_day),
                location=_clean(meeting.location, MAX_LOCATION_LENGTH) if meeting.location else None,
            )
        )
    result.sort(key=lambda item: item.start_at)
    return result[:MAX_MEETINGS]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _due_text(task: BriefingTask) -> str:
    if task.urgency == URGENCY_OVERDUE:
        return f"OVERDUE by {_plural(task.days_overdue, 'day')} (due {task.due_date.isoformat()})"
    if task.urgency == URGENCY_TODAY:
        return "DUE TODAY"
    if task.urgency == URGENCY_UPCOMING:
        return f"due {task.due_date.isoformat()}"
    return "no due date"


def build_daily_briefing_dossier(
    tasks: list[BriefingTask],
    meetings: list[BriefingMeeting],
    now_local: datetime,
    total_open_tasks: int,
) -> str:
    """The user's workload as text, between markers so it reads as data."""
    lines = [
        DOSSIER_START,
        f"Today: {now_local.strftime('%A')}, {now_local.day} {now_local.strftime('%B %Y')}",
        f"Current time: {_clock(now_local)} ({now_local.tzinfo})",
        "",
        f"OPEN TASKS ({len(tasks)} listed of {total_open_tasks} open)",
    ]

    if not tasks:
        lines.append("(none)")

    for task in tasks:
        parts = [
            f"[{task.ref}] {_quoted(task.subject)}",
            f"priority {task.priority}",
            f"status {task.status}",
            _due_text(task),
        ]
        if task.related_to:
            parts.append(f"related: {task.related_to}")
        lines.append(" | ".join(parts))
        if task.description:
            lines.append(f"    note: {task.description}")

    lines += ["", "MEETINGS STILL TO COME TODAY (hosted by this user)"]
    if not meetings:
        lines.append("(none)")

    for meeting in meetings:
        when = (
            "all day"
            if meeting.is_all_day
            else f"{_clock(meeting.start_at)} - {_clock(meeting.end_at)}"
        )
        line = f"- {when} | {_quoted(meeting.title)}"
        if meeting.location:
            line += f" | location: {meeting.location}"
        lines.append(line)

    lines += ["", DOSSIER_END]
    return "\n".join(lines)
