import unittest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.modules.meetings.application.dto.create_meeting import CreateMeetingDTO
from src.modules.meetings.application.dto.get_meeting import GetMeetingDTO, MeetingParticipantDTO, MeetingRelatedRecordDTO
from src.modules.meetings.application.dto.get_meetings import GetMeetingsDTO
from src.modules.meetings.application.dto.participant_group import ParticipantGroup
from src.modules.meetings.application.dto.update_meeting import UpdateMeetingDTO
from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.meetings.application.use_cases.create_meeting import CreateMeetingUseCase
from src.modules.meetings.application.use_cases.cleanup_orphaned_meetings import CleanupOrphanedMeetingsUseCase
from src.modules.meetings.application.use_cases.delete_meeting import DeleteMeetingUseCase
from src.modules.meetings.application.use_cases.get_meeting import GetMeetingUseCase
from src.modules.meetings.application.use_cases.get_meetings import GetMeetingsUseCase
from src.modules.meetings.application.use_cases.update_meeting import UpdateMeetingUseCase
from src.modules.meetings.domain.entities.meeting import Meeting
from src.modules.meetings.domain.enums.meeting_participant_type import MeetingParticipantType
from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User


class FakeTransaction:
    def execute(self, operation):
        return operation()


class FakeTimelineRecorder:
    def __init__(self):
        self.events = []

    def record(
        self,
        event_type,
        actor_id,
        message,
        metadata,
        targets,
    ):
        self.events.append(
            {
                "event_type": event_type,
                "actor_id": actor_id,
                "message": message,
                "metadata": metadata,
                "targets": targets,
            }
        )


class FakeUserRepo:
    def __init__(self, users):
        self.users = users

    def get_by_id(self, user_id):
        return self.users.get(user_id)


class FakeLead:
    def __init__(self, id, name="Lead", is_deleted=False):
        self.id = id
        self.name = name
        self.is_deleted = is_deleted


class FakeContact:
    def __init__(self, id, name="Contact", is_deleted=False):
        self.id = id
        self.name = name
        self.is_deleted = is_deleted


class FakeLeadRepo:
    def __init__(self, leads):
        self.leads = leads

    def get_by_id(self, lead_id):
        return self.leads.get(lead_id)


class FakeContactRepo:
    def __init__(self, contacts):
        self.contacts = contacts

    def get_by_id(self, contact_id):
        return self.contacts.get(contact_id)


class FakeMeetingRepo(MeetingRepository):
    def __init__(self):
        self.meetings = {}
        self.details = {}
        self.replaced = []
        self.orphaned = []

    def save(self, meeting):
        self.meetings[meeting.id] = meeting
        return meeting

    def save_with_relationships(
        self,
        meeting,
        related_record_type=None,
        related_record_ids=(),
        participant_groups=(),
    ):
        self.meetings[meeting.id] = meeting

        self.replaced.append(
            (
                meeting.id,
                related_record_type,
                related_record_ids,
                participant_groups,
            )
        )

        return meeting

    def get_by_id(self, meeting_id):
        return self.meetings.get(meeting_id)

    def get_by_id_with_details(self, meeting_id):
        return self.details.get(meeting_id)

    def get_all(self, query):
        return PaginatedResult(
            [],
            query.page,
            query.page_size,
            0,
        )

    def replace_relationships(
        self,
        meeting_id,
        related_record_type,
        related_record_ids,
        participant_groups,
    ):
        self.replaced.append(
            (
                meeting_id,
                related_record_type,
                related_record_ids,
                participant_groups,
            )
        )

    def soft_delete_by_id(self, meeting_id):
        meeting = self.meetings.get(meeting_id)

        if not meeting:
            return None

        meeting.is_deleted = True
        return meeting

    def soft_delete_if_orphaned(self, record_type, record_id):
        self.orphaned.append(
            (
                record_type,
                record_id,
            )
        )

        return []


def user():
    now = datetime.now(timezone.utc)

    u = User(
        uuid4(),
        "User",
        "user@example.com",
        UserRole.ADMIN,
        True,
        now,
        now,
    )

    return u


class MeetingApplicationTests(unittest.TestCase):

    def setUp(self):
        self.u = user()

        self.lead = FakeLead(uuid4())
        self.contact = FakeContact(uuid4())

        self.users = {
            self.u.id: self.u,
        }

        self.leads = {
            self.lead.id: self.lead,
        }

        self.contacts = {
            self.contact.id: self.contact,
        }

        self.repo = FakeMeetingRepo()
        self.tx = FakeTransaction()

        # Fake TimelineRecorder used by all use cases that
        # now depend on the timeline application interface.
        self.timeline = FakeTimelineRecorder()

        self.usecase = CreateMeetingUseCase(
            self.repo,
            FakeUserRepo(self.users),
            FakeLeadRepo(self.leads),
            FakeContactRepo(self.contacts),
            self.timeline,
            self.tx,
        )

    def dto(self, **kw):
        now = datetime.now(timezone.utc)

        data = dict(
            title="Demo",
            start_at=now,
            end_at=now + timedelta(hours=1),
            host_id=self.u.id,
            created_by_id=self.u.id,
        )

        data.update(kw)

        return CreateMeetingDTO(**data)

    def test_create_valid(self):
        m = self.usecase.execute(self.dto())

        self.assertEqual(m.title, "Demo")
        self.assertFalse(m.is_deleted)

    def test_create_records_timeline_event(self):
        m = self.usecase.execute(self.dto())

        self.assertEqual(
            len(self.timeline.events),
            1,
        )

        event = self.timeline.events[0]

        self.assertEqual(
            event["event_type"],
            "MEETING_CREATED",
        )

        self.assertEqual(
            event["actor_id"],
            m.created_by_id,
        )

        self.assertEqual(
            event["targets"],
            [("MEETING", m.id)],
        )

    def test_create_rejects_invalid_time(self):
        now = datetime.now(timezone.utc)

        with self.assertRaises(ValueError):
            self.usecase.execute(
                self.dto(
                    start_at=now,
                    end_at=now - timedelta(minutes=1),
                )
            )

    def test_create_validates_related_lead(self):
        m = self.usecase.execute(
            self.dto(
                related_record_type=MeetingRelatedRecordType.LEAD,
                related_record_ids=(self.lead.id,),
            )
        )

        self.assertIsNotNone(m)

        self.assertEqual(
            self.timeline.events[-1]["targets"],
            [
                ("MEETING", m.id),
                (MeetingRelatedRecordType.LEAD.value, self.lead.id),
            ],
        )

    def test_create_rejects_mixed_related_type_at_application_boundary(self):
        with self.assertRaises(ValueError):
            self.usecase.execute(
                self.dto(
                    related_record_type=MeetingRelatedRecordType.LEAD,
                    related_record_ids=(
                        self.lead.id,
                        self.contact.id,
                    ),
                )
            )

    def test_create_all_participant_types(self):
        p = ParticipantGroup(
            MeetingParticipantType.LEAD,
            (self.lead.id,),
        )

        c = ParticipantGroup(
            MeetingParticipantType.CONTACT,
            (self.contact.id,),
        )

        u = ParticipantGroup(
            MeetingParticipantType.USER,
            (self.u.id,),
        )

        self.usecase.execute(
            self.dto(
                participant_groups=(p, c, u),
            )
        )

        self.assertEqual(
            len(self.repo.replaced[-1][3]),
            3,
        )

    def test_get_list(self):
        uc = GetMeetingsUseCase(self.repo)

        result = uc.execute(
            ListQuery()
        )

        self.assertEqual(
            result.total,
            0,
        )

    def test_get_detail(self):
        m = self.usecase.execute(
            self.dto()
        )

        detail = GetMeetingDTO(
            m,
            m.host_id,
            "User",
            m.created_by_id,
            "User",
            (),
            (),
        )

        self.repo.details[m.id] = detail

        self.assertEqual(
            GetMeetingUseCase(self.repo).execute(m.id),
            detail,
        )

    def add_meeting_detail(self, meeting):
        detail = GetMeetingDTO(
            meeting,
            meeting.host_id,
            "User",
            meeting.created_by_id,
            "User",
            (),
            (),
        )

        self.repo.details[meeting.id] = detail
        return detail

    def test_update_core_fields(self):
        m = self.usecase.execute(
            self.dto()
        )

        self.add_meeting_detail(m)

        updated = UpdateMeetingUseCase(
            self.repo,
            FakeUserRepo(self.users),
            FakeLeadRepo(self.leads),
            FakeContactRepo(self.contacts),
            self.timeline,
            self.tx,
        ).execute(
            UpdateMeetingDTO(
                m.id,
                {
                    "title": "Updated",
                },
            )
        )

        self.assertEqual(
            updated.title,
            "Updated",
        )

    def test_update_related(self):
        m = self.usecase.execute(
            self.dto()
        )

        self.add_meeting_detail(m)

        uc = UpdateMeetingUseCase(
            self.repo,
            FakeUserRepo(self.users),
            FakeLeadRepo(self.leads),
            FakeContactRepo(self.contacts),
            self.timeline,
            self.tx,
        )

        uc.execute(
            UpdateMeetingDTO(
                m.id,
                {},
                MeetingRelatedRecordType.LEAD,
                (self.lead.id,),
                (),
            )
        )

        self.assertEqual(
            self.repo.replaced[-1][2],
            (self.lead.id,),
        )

    def test_delete_soft(self):
        m = self.usecase.execute(
            self.dto()
        )

        self.add_meeting_detail(m)

        DeleteMeetingUseCase(
            self.repo,
            self.timeline,
            self.tx,
        ).execute(
            m.id
        )

        self.assertTrue(
            self.repo.meetings[m.id].is_deleted
        )

    def test_delete_missing(self):
        with self.assertRaises(ValueError):
            DeleteMeetingUseCase(
                self.repo,
                self.timeline,
                self.tx,
            ).execute(
                uuid4()
            )

    def test_zero_related_is_allowed(self):
        self.usecase.execute(
            self.dto()
        )

        self.assertEqual(
            self.repo.replaced[-1][1],
            None,
        )

    def test_orphan_cleanup_is_repository_driven(self):
        result = CleanupOrphanedMeetingsUseCase(
            self.repo
        ).execute(
            MeetingRelatedRecordType.LEAD,
            self.lead.id,
        )

        self.assertEqual(
            result,
            [],
        )

        self.assertEqual(
            self.repo.orphaned[-1],
            (
                MeetingRelatedRecordType.LEAD,
                self.lead.id,
            ),
        )


if __name__ == "__main__":
    unittest.main()