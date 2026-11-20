from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

# Where a task sits in the plan. The order is the order they are shown in.
BUCKET_DO_FIRST = "do_first"
BUCKET_DO_NEXT = "do_next"
BUCKET_CAN_WAIT = "can_wait"
BUCKETS = (BUCKET_DO_FIRST, BUCKET_DO_NEXT, BUCKET_CAN_WAIT)

# How close a task's due date is, computed by the server (never by the model).
URGENCY_OVERDUE = "overdue"
URGENCY_TODAY = "today"
URGENCY_UPCOMING = "upcoming"
URGENCY_NO_DUE_DATE = "no_due_date"


@dataclass(frozen=True)
class BriefingTask:
    """One open task as the briefing sees it.

    ``ref`` ("T1", "T2", ...) is the short handle the model uses instead of the
    task's UUID, so a mistyped id can never point at someone else's record.
    """

    ref: str
    id: UUID
    subject: str
    priority: str
    status: str
    due_date: date | None
    urgency: str
    days_overdue: int
    related_to: str | None
    description: str | None


@dataclass(frozen=True)
class BriefingMeeting:
    """A meeting the user hosts that has not ended yet today (caller's time zone)."""

    title: str
    start_at: datetime
    end_at: datetime
    is_all_day: bool
    location: str | None


@dataclass(frozen=True)
class PriorityPick:
    """One line of the model's plan: which task, in which bucket, and why."""

    ref: str
    bucket: str
    reason: str


@dataclass(frozen=True)
class DailyBriefingResult:
    """What the briefing generator hands back (no task data, only the text)."""

    headline: str
    priorities: list[PriorityPick] = field(default_factory=list)
    heads_up: list[str] = field(default_factory=list)
    model_name: str | None = None


@dataclass(frozen=True)
class PrioritizedTaskDTO:
    """A plan entry joined with the real task.

    Everything except ``bucket`` and ``reason`` comes from the database, so the
    subject and dates shown are always the task's own, never the model's wording.
    """

    rank: int
    task_id: UUID
    subject: str
    priority: str
    status: str
    due_date: date | None
    urgency: str
    days_overdue: int
    related_to: str | None
    bucket: str
    reason: str


@dataclass(frozen=True)
class DailyBriefingCountsDTO:
    overdue_tasks: int
    due_today_tasks: int
    meetings_today: int
    # True number of open tasks of the user (can be more than the plan looked at).
    open_tasks_total: int
    # How many of them the plan was written from.
    tasks_considered: int


@dataclass(frozen=True)
class DailyBriefingDTO:
    """Read model of ``POST /dashboard/briefing/``."""

    date: date
    generated_at: datetime
    model_name: str | None
    headline: str
    counts: DailyBriefingCountsDTO
    priorities: list[PrioritizedTaskDTO]
    heads_up: list[str]
