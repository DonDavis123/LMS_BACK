from datetime import timedelta
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from src.modules.shared.tests.tenancy.factories import default_test_company
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.meetings.application.dto.related_group import RelatedGroup
from src.modules.meetings.domain.entities.meeting import Meeting
from src.modules.meetings.domain.enums.meeting_participant_type import (
    MeetingParticipantType,
)
from src.modules.meetings.domain.enums.meeting_related_record_type import (
    MeetingRelatedRecordType,
)
from src.modules.meetings.infrastructure.persistence.django_meeting_repository import (
    DjangoMeetingRepository,
    ParticipantGroup,
)
from src.modules.meetings.infrastructure.persistence.models import (
    DjangoMeetingModel,
    DjangoMeetingParticipantModel,
    DjangoMeetingRelatedRecordModel,
)
from src.modules.users.infrastructure.persistence.models import User


class MeetingDomainTests(TestCase):
    def test_create_meeting_generates_uuid_and_defaults_to_active(self):
        now = timezone.now()
        meeting = Meeting.create(
            title="Client Discussion",
            start_at=now,
            end_at=now + timedelta(hours=1),
            host_id=uuid4(),
            created_by_id=uuid4(),
        )

        self.assertIsNotNone(meeting.id)
        self.assertFalse(meeting.is_deleted)
        self.assertEqual(meeting.title, "Client Discussion")

    def test_create_rejects_empty_title(self):
        now = timezone.now()

        with self.assertRaises(ValueError):
            Meeting.create(
                title="   ",
                start_at=now,
                end_at=now + timedelta(hours=1),
                host_id=uuid4(),
                created_by_id=uuid4(),
            )

    def test_create_rejects_end_before_start(self):
        now = timezone.now()

        with self.assertRaises(ValueError):
            Meeting.create(
                title="Invalid Meeting",
                start_at=now,
                end_at=now - timedelta(minutes=1),
                host_id=uuid4(),
                created_by_id=uuid4(),
            )

    def test_soft_delete_and_already_deleted_behavior(self):
        now = timezone.now()
        meeting = Meeting.create(
            title="Client Discussion",
            start_at=now,
            end_at=now + timedelta(hours=1),
            host_id=uuid4(),
            created_by_id=uuid4(),
        )

        meeting.soft_delete()
        self.assertTrue(meeting.is_deleted)

        with self.assertRaises(ValueError):
            meeting.soft_delete()


class MeetingInfrastructureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(company=default_test_company(),
            email="meeting-owner@example.com",
            password="meeting-password",
            name="Meeting Owner",
            role=User.Role.ADMIN,
        )
        self.second_user = User.objects.create_user(company=default_test_company(),
            email="meeting-user@example.com",
            password="meeting-password",
            name="Meeting User",
            role=User.Role.ADMIN,
        )
        self.lead = DjangoLeadModel.objects.create(company=default_test_company(),
            name="Meeting Lead",
            company_name="Meeting Company",
            owner=self.user,
        )
        self.second_lead = DjangoLeadModel.objects.create(company=default_test_company(),
            name="Second Lead",
            company_name="Second Company",
            owner=self.user,
        )
        now = timezone.now()
        self.contact = DjangoContactModel.objects.create(company=default_test_company(),
            name="Meeting Contact",
            contact_owner=self.user,
            created_by=self.user,
            created_at=now,
            modified_by=self.user,
            updated_at=now,
        )
        self.second_contact = DjangoContactModel.objects.create(company=default_test_company(),
            name="Second Contact",
            contact_owner=self.user,
            created_by=self.user,
            created_at=now,
            modified_by=self.user,
            updated_at=now,
        )
        self.repository = DjangoMeetingRepository(company_id=default_test_company().id)

    def _meeting(self):
        now = timezone.now()
        return Meeting.create(
            title="Client Discussion",
            description="Discuss requirements.",
            location="Google Meet",
            start_at=now,
            end_at=now + timedelta(hours=1),
            host_id=self.user.id,
            created_by_id=self.user.id,
        )

    def test_save_and_get_active_meeting(self):
        meeting = self._meeting()
        self.repository.save(meeting)

        result = self.repository.get_by_id(meeting.id)

        self.assertIsNotNone(result)
        self.assertEqual(result.id, meeting.id)
        self.assertEqual(result.title, "Client Discussion")

    def test_soft_deleted_meeting_is_hidden_from_active_lookup(self):
        meeting = self._meeting()
        self.repository.save(meeting)

        self.repository.soft_delete_by_id(meeting.id)

        self.assertIsNone(self.repository.get_by_id(meeting.id))
        self.assertTrue(
            DjangoMeetingModel.objects.get(id=meeting.id).is_deleted
        )

    def test_multiple_related_leads_are_allowed(self):
        meeting = self._meeting()
        self.repository.save_with_relationships(
            meeting,
            related_groups=(
                RelatedGroup(
                    MeetingRelatedRecordType.LEAD,
                    (self.lead.id, self.second_lead.id),
                ),
            ),
        )

        self.assertEqual(
            DjangoMeetingRelatedRecordModel.objects.filter(
                meeting_id=meeting.id,
                record_type=MeetingRelatedRecordType.LEAD.value,
            ).count(),
            2,
        )

    def test_multiple_related_contacts_are_allowed(self):
        meeting = self._meeting()
        self.repository.save_with_relationships(
            meeting,
            related_groups=(
                RelatedGroup(
                    MeetingRelatedRecordType.CONTACT,
                    (self.contact.id, self.second_contact.id),
                ),
            ),
        )

        self.assertEqual(
            DjangoMeetingRelatedRecordModel.objects.filter(
                meeting_id=meeting.id,
                record_type=MeetingRelatedRecordType.CONTACT.value,
            ).count(),
            2,
        )

    def test_related_to_can_mix_leads_and_contacts(self):
        meeting = self._meeting()
        self.repository.save_with_relationships(
            meeting,
            related_groups=(
                RelatedGroup(
                    MeetingRelatedRecordType.LEAD,
                    (self.lead.id, self.second_lead.id),
                ),
                RelatedGroup(
                    MeetingRelatedRecordType.CONTACT,
                    (self.contact.id, self.second_contact.id),
                ),
            ),
        )

        detail = self.repository.get_by_id_with_details(meeting.id)
        self.assertEqual(len(detail.related_to), 4)
        self.assertEqual(
            {item.record_type for item in detail.related_to},
            {MeetingRelatedRecordType.LEAD, MeetingRelatedRecordType.CONTACT},
        )

    def test_replace_relationships_replaces_the_whole_selection(self):
        meeting = self._meeting()
        self.repository.save_with_relationships(
            meeting,
            related_groups=(
                RelatedGroup(MeetingRelatedRecordType.LEAD, (self.lead.id,)),
            ),
        )

        self.repository.replace_relationships(
            meeting.id,
            (
                RelatedGroup(MeetingRelatedRecordType.LEAD, (self.second_lead.id,)),
                RelatedGroup(MeetingRelatedRecordType.CONTACT, (self.contact.id,)),
            ),
            (),
        )

        detail = self.repository.get_by_id_with_details(meeting.id)
        self.assertEqual(
            {item.id for item in detail.related_to},
            {self.second_lead.id, self.contact.id},
        )

        self.repository.replace_relationships(meeting.id, (), ())
        detail = self.repository.get_by_id_with_details(meeting.id)
        self.assertEqual(detail.related_to, ())

    def test_same_type_listed_in_two_groups_is_rejected(self):
        meeting = self._meeting()

        with self.assertRaises(ValueError):
            self.repository.save_with_relationships(
                meeting,
                related_groups=(
                    RelatedGroup(MeetingRelatedRecordType.LEAD, (self.lead.id,)),
                    RelatedGroup(MeetingRelatedRecordType.LEAD, (self.lead.id,)),
                ),
            )

    def test_meeting_survives_when_one_related_type_is_deleted(self):
        meeting = self._meeting()
        self.repository.save_with_relationships(
            meeting,
            related_groups=(
                RelatedGroup(MeetingRelatedRecordType.LEAD, (self.lead.id,)),
                RelatedGroup(MeetingRelatedRecordType.CONTACT, (self.contact.id,)),
            ),
        )

        self.lead.is_deleted = True
        self.lead.save(update_fields=["is_deleted"])

        deleted = self.repository.soft_delete_if_orphaned(
            MeetingRelatedRecordType.LEAD,
            self.lead.id,
        )

        self.assertEqual(deleted, [])
        self.assertIsNotNone(self.repository.get_by_id(meeting.id))

    def test_meeting_is_deleted_when_every_related_record_is_deleted(self):
        meeting = self._meeting()
        self.repository.save_with_relationships(
            meeting,
            related_groups=(
                RelatedGroup(MeetingRelatedRecordType.LEAD, (self.lead.id,)),
                RelatedGroup(MeetingRelatedRecordType.CONTACT, (self.contact.id,)),
            ),
        )

        self.lead.is_deleted = True
        self.lead.save(update_fields=["is_deleted"])
        self.contact.is_deleted = True
        self.contact.save(update_fields=["is_deleted"])

        deleted = self.repository.soft_delete_if_orphaned(
            MeetingRelatedRecordType.CONTACT,
            self.contact.id,
        )

        self.assertEqual(deleted, [meeting.id])

    def test_all_participant_types_can_be_used_together(self):
        meeting = self._meeting()
        self.repository.save_with_relationships(
            meeting,
            participant_groups=(
                ParticipantGroup(
                    MeetingParticipantType.LEAD,
                    (self.lead.id,),
                ),
                ParticipantGroup(
                    MeetingParticipantType.USER,
                    (self.user.id, self.second_user.id),
                ),
                ParticipantGroup(
                    MeetingParticipantType.CONTACT,
                    (self.contact.id,),
                ),
            ),
        )

        self.assertEqual(
            DjangoMeetingParticipantModel.objects.filter(
                meeting_id=meeting.id,
            ).count(),
            4,
        )

    def test_duplicate_participant_is_rejected(self):
        meeting = self._meeting()
        self.repository.save_with_relationships(
            meeting,
            participant_groups=(
                ParticipantGroup(
                    MeetingParticipantType.USER,
                    (self.user.id,),
                ),
            ),
        )

        with self.assertRaises(ValueError):
            self.repository.add_participants(
                meeting.id,
                MeetingParticipantType.USER,
                (self.user.id,),
            )

    def test_duplicate_related_record_is_rejected(self):
        meeting = self._meeting()
        self.repository.save_with_relationships(
            meeting,
            related_groups=(
                RelatedGroup(MeetingRelatedRecordType.LEAD, (self.lead.id,)),
            ),
        )

        with self.assertRaises(ValueError):
            self.repository.add_related_records(
                meeting.id,
                MeetingRelatedRecordType.LEAD,
                (self.lead.id,),
            )

    def test_invalid_relationship_rolls_back_meeting_creation(self):
        meeting = self._meeting()

        with self.assertRaises(ValueError):
            self.repository.save_with_relationships(
                meeting,
                related_groups=(
                    RelatedGroup(
                        MeetingRelatedRecordType.LEAD,
                        (self.lead.id, self.lead.id),
                    ),
                ),
            )

        self.assertFalse(
            DjangoMeetingModel.objects.filter(id=meeting.id).exists()
        )
