from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.tasks.infrastructure.persistence.models import DjangoTaskModel
from src.modules.users.infrastructure.persistence.models import User


class TaskApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="task-owner@example.com",
            password="task-password",
            name="Task Owner",
            role=User.Role.ADMIN,
        )
        now = timezone.now()

        self.lead = DjangoLeadModel.objects.create(
            name="Task Lead",
            company_name="Example Company",
            owner=self.user,
        )
        self.account = DjangoAccountModel.objects.create(
            account_owner=self.user,
            account_name="Task Account",
            created_by=self.user,
            created_at=now,
            modified_by=self.user,
            updated_at=now,
        )
        self.contact = DjangoContactModel.objects.create(
            account=self.account,
            contact_owner=self.user,
            name="Task Contact",
            created_by=self.user,
            created_at=now,
            modified_by=self.user,
            updated_at=now,
        )

    def _task_payload(self, **overrides):
        payload = {
            "subject": "Follow up with client",
            "owner_id": str(self.user.id),
            "priority": "High",
            "status": "Not Started",
        }
        payload.update(overrides)
        return payload

    def test_tasks_require_authentication(self):
        response = self.client.get("/api/tasks/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_read_update_and_soft_delete_task(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            "/api/tasks/",
            self._task_payload(contact_id=str(self.contact.id)),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["priority"], "High")
        task_id = response.data["id"]

        response = self.client.get(f"/api/tasks/{task_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(
            f"/api/tasks/{task_id}/",
            {"subject": "Updated follow up"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["subject"], "Updated follow up")

        response = self.client.patch(
            f"/api/tasks/{task_id}/",
            {"lead_id": str(self.lead.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.delete(f"/api/tasks/{task_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        task = DjangoTaskModel.objects.get(id=task_id)
        self.assertTrue(task.is_deleted)

        response = self.client.get(f"/api/tasks/{task_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.get("/api/tasks/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_valid_task_relationships(self):
        self.client.force_authenticate(self.user)

        valid_payloads = [
            self._task_payload(lead_id=str(self.lead.id)),
            self._task_payload(contact_id=str(self.contact.id)),
            self._task_payload(
                contact_id=str(self.contact.id),
                account_id=str(self.account.id),
            ),
        ]

        for payload in valid_payloads:
            response = self.client.post(
                "/api/tasks/",
                payload,
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invalid_task_relationships_are_rejected(self):
        self.client.force_authenticate(self.user)

        invalid_payloads = [
            self._task_payload(
                lead_id=str(self.lead.id),
                contact_id=str(self.contact.id),
            ),
            self._task_payload(
                lead_id=str(self.lead.id),
                account_id=str(self.account.id),
            ),
            self._task_payload(account_id=str(self.account.id)),
        ]

        for payload in invalid_payloads:
            response = self.client.post(
                "/api/tasks/",
                payload,
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
