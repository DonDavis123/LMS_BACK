from datetime import timedelta
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from src.modules.meetings.infrastructure.persistence.models.django_meeting_model import DjangoMeetingModel
from src.modules.tasks.infrastructure.persistence.models.django_task_model import DjangoTaskModel
from src.modules.timeline.domain.enums.timeline_entity_type import TimelineEntityType
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder
from src.modules.users.infrastructure.persistence.models import User


class TaskMeetingTimelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email=f"timeline-{uuid4()}@example.com",
            password="password",
            name="Timeline User",
            role=User.Role.ADMIN,
        )
        self.repository = DjangoTimelineRepository()
        self.recorder = DefaultTimelineRecorder(self.repository)

    def test_task_is_a_valid_timeline_entity(self):
        task = DjangoTaskModel.objects.create(
            subject="Timeline Task",
            owner=self.user,
            created_by=self.user,
        )

        self.assertTrue(
            self.repository.entity_exists(
                TimelineEntityType.TASK.value,
                task.id,
            )
        )

        self.recorder.record(
            event_type="TASK_CREATED",
            actor_id=self.user.id,
            message="Task Timeline Task was created.",
            metadata={"task_id": str(task.id)},
            targets=[(TimelineEntityType.TASK.value, task.id)],
        )

        events = self.repository.get_for_entity(
            TimelineEntityType.TASK.value,
            task.id,
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "TASK_CREATED")

    def test_meeting_is_a_valid_timeline_entity(self):
        now = timezone.now()
        meeting = DjangoMeetingModel.objects.create(
            title="Timeline Meeting",
            start_at=now,
            end_at=now + timedelta(hours=1),
            host=self.user,
            created_by=self.user,
        )

        self.assertTrue(
            self.repository.entity_exists(
                TimelineEntityType.MEETING.value,
                meeting.id,
            )
        )

        self.recorder.record(
            event_type="MEETING_CREATED",
            actor_id=self.user.id,
            message="Meeting Timeline Meeting was created.",
            metadata={"meeting_id": str(meeting.id)},
            targets=[(TimelineEntityType.MEETING.value, meeting.id)],
        )

        events = self.repository.get_for_entity(
            TimelineEntityType.MEETING.value,
            meeting.id,
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "MEETING_CREATED")
