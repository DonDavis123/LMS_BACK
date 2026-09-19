from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.contacts.infrastructure.persistence.django_contact_model import DjangoContactModel
from src.modules.leads.infrastructure.persistence.django_lead_model import DjangoLeadModel
from src.modules.meetings.infrastructure.persistence.models import (
    DjangoMeetingModel,
    DjangoMeetingParticipantModel,
    DjangoMeetingRelatedRecordModel,
)
from src.modules.users.infrastructure.persistence.models import User


class MeetingPresentationApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="meeting-api@example.com",
            password="password",
            name="Meeting API User",
            role=User.Role.ADMIN,
        )
        self.other_user = User.objects.create_user(
            email="meeting-api-other@example.com",
            password="password",
            name="Other Meeting User",
            role=User.Role.ADMIN,
        )
        self.lead = DjangoLeadModel.objects.create(
            name="API Lead",
            company_name="API Company",
            owner=self.user,
        )
        self.second_lead = DjangoLeadModel.objects.create(
            name="Second API Lead",
            company_name="Second API Company",
            owner=self.user,
        )
        now = timezone.now()
        self.contact = DjangoContactModel.objects.create(
            name="API Contact",
            contact_owner=self.user,
            created_by=self.user,
            created_at=now,
            modified_by=self.user,
            updated_at=now,
        )
        self.client.force_authenticate(self.user)

    def _payload(self, **overrides):
        now = timezone.now()
        payload = {
            "title": "Client Meeting",
            "description": "Discuss requirements",
            "location": "Kochi",
            "is_all_day": False,
            "start_at": now.isoformat(),
            "end_at": (now + timedelta(hours=1)).isoformat(),
            "host_id": str(self.user.id),
        }
        payload.update(overrides)
        return payload

    def _create_meeting(self, **overrides):
        response = self.client.post("/api/meetings/", self._payload(**overrides), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data["id"]

    def test_meeting_endpoints_require_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/meetings/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.post("/api/meetings/", self._payload(), format="json").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_meeting_with_related_record_and_all_participant_types(self):
        response = self.client.post(
            "/api/meetings/",
            self._payload(
                related_to={"type": "LEAD", "ids": [str(self.lead.id), str(self.second_lead.id)]},
                participants={
                    "leads": [str(self.lead.id)],
                    "contacts": [str(self.contact.id)],
                    "users": [str(self.other_user.id)],
                },
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        meeting_id = response.data["id"]
        self.assertEqual(
            DjangoMeetingRelatedRecordModel.objects.filter(meeting_id=meeting_id).count(),
            2,
        )
        self.assertEqual(
            DjangoMeetingParticipantModel.objects.filter(meeting_id=meeting_id).count(),
            3,
        )

    def test_duplicate_participant_is_rejected_by_application_layer(self):
        response = self.client.post(
            "/api/meetings/",
            self._payload(
                participants={"users": [str(self.other_user.id), str(self.other_user.id)]},
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_returns_pagination_metadata(self):
        self._create_meeting()
        self._create_meeting()

        response = self.client.get("/api/meetings/?page=1&page_size=1")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page"], 1)
        self.assertEqual(response.data["pagination"]["page_size"], 1)
        self.assertEqual(response.data["pagination"]["total"], 2)
        self.assertEqual(response.data["pagination"]["total_pages"], 2)
        self.assertEqual(len(response.data["results"]), 1)

    def test_detail_returns_meeting_related_to_and_participants(self):
        meeting_id = self._create_meeting(
            related_to={"type": "CONTACT", "ids": [str(self.contact.id)]},
            participants={"users": [str(self.other_user.id)]},
        )

        response = self.client.get(f"/api/meetings/{meeting_id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], meeting_id)
        self.assertEqual(response.data["host"]["id"], str(self.user.id))
        self.assertEqual(response.data["related_to"][0]["record_type"], "CONTACT")
        self.assertEqual(response.data["participants"][0]["participant_type"], "USER")

    def test_detail_returns_404_for_missing_meeting(self):
        import uuid

        response = self.client.get(f"/api/meetings/{uuid.uuid4()}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_preserves_omitted_relationships(self):
        meeting_id = self._create_meeting(
            related_to={"type": "LEAD", "ids": [str(self.lead.id)]},
            participants={"contacts": [str(self.contact.id)]},
        )

        response = self.client.patch(
            f"/api/meetings/{meeting_id}/",
            {"title": "Updated Meeting"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            DjangoMeetingRelatedRecordModel.objects.filter(meeting_id=meeting_id).count(),
            1,
        )
        self.assertEqual(
            DjangoMeetingParticipantModel.objects.filter(meeting_id=meeting_id).count(),
            1,
        )

    def test_update_can_clear_relationships_explicitly(self):
        meeting_id = self._create_meeting(
            related_to={"type": "LEAD", "ids": [str(self.lead.id)]},
            participants={"contacts": [str(self.contact.id)]},
        )

        response = self.client.patch(
            f"/api/meetings/{meeting_id}/",
            {"related_to": None, "participants": None},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(DjangoMeetingRelatedRecordModel.objects.filter(meeting_id=meeting_id).count(), 0)
        self.assertEqual(DjangoMeetingParticipantModel.objects.filter(meeting_id=meeting_id).count(), 0)

    def test_update_replaces_participants(self):
        meeting_id = self._create_meeting(
            participants={"contacts": [str(self.contact.id)]},
        )

        response = self.client.patch(
            f"/api/meetings/{meeting_id}/",
            {"participants": {"users": [str(self.other_user.id)]}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        participant = DjangoMeetingParticipantModel.objects.get(meeting_id=meeting_id)
        self.assertEqual(participant.user_id, self.other_user.id)
        self.assertIsNone(participant.contact_id)

    def test_invalid_host_is_rejected(self):
        import uuid

        response = self.client.post(
            "/api/meetings/",
            self._payload(host_id=str(uuid.uuid4())),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_end_before_start_is_rejected(self):
        now = timezone.now()
        response = self.client.post(
            "/api/meetings/",
            self._payload(
                start_at=now.isoformat(),
                end_at=(now - timedelta(minutes=1)).isoformat(),
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_soft_deletes_meeting_and_hides_it(self):
        meeting_id = self._create_meeting()

        response = self.client.delete(f"/api/meetings/{meeting_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        self.assertTrue(DjangoMeetingModel.objects.get(id=meeting_id).is_deleted)
        self.assertEqual(
            self.client.get(f"/api/meetings/{meeting_id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get("/api/meetings/").data["pagination"]["total"],
            0,
        )
