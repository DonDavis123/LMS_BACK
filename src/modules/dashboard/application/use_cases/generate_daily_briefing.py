from datetime import datetime, time, timedelta, timezone as dt_timezone
from uuid import UUID

from src.modules.dashboard.application.dto.daily_briefing import (
    BUCKET_CAN_WAIT,
    BUCKET_DO_FIRST,
    BUCKET_DO_NEXT,
    BUCKETS,
    URGENCY_OVERDUE,
    URGENCY_TODAY,
    BriefingTask,
    DailyBriefingCountsDTO,
    DailyBriefingDTO,
    PrioritizedTaskDTO,
)
from src.modules.dashboard.application.interfaces.daily_briefing_generator import (
    DailyBriefingGenerator,
    DailyBriefingUnavailableError,
)
from src.modules.dashboard.application.services.daily_briefing_dossier import (
    MAX_TASKS,
    build_briefing_meetings,
    build_briefing_tasks,
    build_daily_briefing_dossier,
)
from src.modules.dashboard.application.use_cases.get_dashboard_stats import (
    resolve_timezone,
)
from src.modules.meetings.application.interfaces.meeting_repository import (
    MeetingRepository,
)
from src.modules.shared.application.dto.list_query import FilterCondition, ListQuery
from src.modules.tasks.application.interfaces.task_repository import TaskRepository
from src.modules.tasks.domain.enums.task_status import TaskStatus

# The plan never grows beyond this, however many tasks the user has.
MAX_PRIORITIES = 15

_BUCKET_ORDER = {bucket: index for index, bucket in enumerate(BUCKETS)}
_HIGH_PRIORITIES = {"Highest", "High"}


def default_bucket(task: BriefingTask) -> str:
    """Where a task goes when the model did not say (or said something invalid)."""
    if task.urgency in (URGENCY_OVERDUE, URGENCY_TODAY):
        return BUCKET_DO_FIRST if task.priority in _HIGH_PRIORITIES else BUCKET_DO_NEXT
    return BUCKET_CAN_WAIT


def fallback_reason(task: BriefingTask) -> str:
    if task.urgency == URGENCY_OVERDUE:
        days = task.days_overdue
        return f"Overdue by {days} day{'' if days == 1 else 's'}."
    if task.urgency == URGENCY_TODAY:
        return "Due today."
    return ""


class GenerateDailyBriefingUseCase:
    """Writes "what should I work on today, and in which order" for the caller.

    Runs only when the user asks for it. It reads the caller's own open tasks
    (the same "responsible" rule as the dashboard's My tasks list) and the
    meetings they host that are still to come today, both scoped to the
    caller's company by the repositories.

    Nothing is stored. The model only chooses the order and writes the reasons:
    urgency, dates, subjects and counts come from the database, a task the model
    invents is dropped, and an overdue or due-today task it leaves out is added
    back, so the plan can never silently hide late work.
    """

    def __init__(
        self,
        task_repository: TaskRepository,
        meeting_repository: MeetingRepository,
        briefing_generator: DailyBriefingGenerator,
    ):
        self.task_repository = task_repository
        self.meeting_repository = meeting_repository
        self.briefing_generator = briefing_generator

    def execute(
        self,
        user_id: UUID,
        timezone_name: str,
        now: datetime | None = None,
    ) -> DailyBriefingDTO:
        # Check the setup first: no point reading the workload without a model.
        if not self.briefing_generator.is_configured():
            raise DailyBriefingUnavailableError("The daily briefing is not configured.")

        tz = resolve_timezone(timezone_name)
        now = now or datetime.now(dt_timezone.utc)
        now_local = now.astimezone(tz)
        today = now_local.date()

        page = self.task_repository.get_all_with_relations(
            ListQuery(
                filters=(
                    FilterCondition("responsible", "equals", str(user_id)),
                    FilterCondition("status", "not_equals", TaskStatus.COMPLETED.value),
                ),
                page=1,
                page_size=MAX_TASKS,
                sort_by="due_date",
                sort_direction="asc",
            )
        )
        tasks = build_briefing_tasks(page.results, today)

        start_of_day = datetime.combine(today, time.min, tzinfo=tz)
        meetings = build_briefing_meetings(
            [
                meeting
                for meeting in self.meeting_repository.get_by_start_at_range(
                    start_of_day, start_of_day + timedelta(days=1)
                )
                if meeting.host_id == user_id
            ],
            tz,
            now,
        )

        counts = DailyBriefingCountsDTO(
            overdue_tasks=sum(1 for task in tasks if task.urgency == URGENCY_OVERDUE),
            due_today_tasks=sum(1 for task in tasks if task.urgency == URGENCY_TODAY),
            meetings_today=len(meetings),
            open_tasks_total=page.total,
            tasks_considered=len(tasks),
        )

        # Nothing to plan: answer directly instead of paying for a model request
        # that could only invent work.
        if not tasks and not meetings:
            return DailyBriefingDTO(
                date=today,
                generated_at=now,
                model_name=None,
                headline="You have no open tasks and no meetings left today. Nothing to prioritise.",
                counts=counts,
                priorities=[],
                heads_up=[],
            )

        dossier = build_daily_briefing_dossier(tasks, meetings, now_local, page.total)

        # Raises DailyBriefingError on failure.
        result = self.briefing_generator.generate(dossier)

        return DailyBriefingDTO(
            date=today,
            generated_at=now,
            model_name=result.model_name,
            headline=result.headline,
            counts=counts,
            priorities=self._join_plan(tasks, result.priorities),
            heads_up=list(result.heads_up),
        )

    @staticmethod
    def _join_plan(tasks: list[BriefingTask], picks) -> list[PrioritizedTaskDTO]:
        by_ref = {task.ref: task for task in tasks}
        chosen: list[tuple[BriefingTask, str, str]] = []
        seen: set[str] = set()

        for pick in picks:
            task = by_ref.get(pick.ref)
            if task is None or task.ref in seen:
                continue  # a task the model made up, or listed twice
            seen.add(task.ref)
            bucket = pick.bucket if pick.bucket in _BUCKET_ORDER else default_bucket(task)
            chosen.append((task, bucket, pick.reason or fallback_reason(task)))

        for task in tasks:
            if task.ref in seen or task.urgency not in (URGENCY_OVERDUE, URGENCY_TODAY):
                continue
            chosen.append((task, default_bucket(task), fallback_reason(task)))

        # Stable: the model's order is kept inside each bucket.
        chosen.sort(key=lambda entry: _BUCKET_ORDER[entry[1]])

        return [
            PrioritizedTaskDTO(
                rank=rank,
                task_id=task.id,
                subject=task.subject,
                priority=task.priority,
                status=task.status,
                due_date=task.due_date,
                urgency=task.urgency,
                days_overdue=task.days_overdue,
                related_to=task.related_to,
                bucket=bucket,
                reason=reason,
            )
            for rank, (task, bucket, reason) in enumerate(chosen[:MAX_PRIORITIES], start=1)
        ]
