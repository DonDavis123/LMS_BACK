import json
import uuid
from datetime import timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.accounts.application.dto.delete_account import DeleteAccountDTO
from src.modules.accounts.application.use_cases.delete_account import (
    DeleteAccountUseCase,
)
from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.calls.infrastructure.persistence.django_call_repository import (
    DjangoCallRepository,
)
from src.modules.calls.infrastructure.persistence.models import DjangoCallModel
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.application.use_cases.delete_lead import DeleteLeadUseCase
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_repository import (
    DjangoLeadRepository,
)
from src.modules.shared.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    default_test_company,
    make_company,
    make_user,
)
from src.modules.tasks.infrastructure.persistence.django_task_repository import (
    DjangoTaskRepository,
)
from src.modules.timeline.infrastructure.persistence.models import (
    TimelineEvent,
    TimelineEventTarget,
)
from src.modules.users.infrastructure.persistence.models import User


def _make_account(company, owner, name):
    now = timezone.now()
    return DjangoAccountModel.objects.create(
        company=company,
        account_owner=owner,
        account_name=name,
        created_by=owner,
        created_at=now,
        modified_by=owner,
        updated_at=now,
    )


def _make_contact(company, owner, name, account=None):
    now = timezone.now()
    return DjangoContactModel.objects.create(
        company=company,
        account=account,
        contact_owner=owner,
        name=name,
        created_by=owner,
        created_at=now,
        modified_by=owner,
        updated_at=now,
    )


def _make_lead(company, owner, name):
    return DjangoLeadModel.objects.create(
        company=company,
        name=name,
        company_name="Example Company",
        owner=owner,
    )


def _filters(field, value):
    return json.dumps(
        [{"field": field, "operator": "equals", "value": str(value)}]
    )


class CallApiTestCase(APITestCase):
    """Shared fixtures: one company with a lead, a contact and an account."""

    def setUp(self):
        self.user = User.objects.create_user(
            company=default_test_company(),
            email="call-owner@example.com",
            password="call-password",
            name="Call Owner",
            role=User.Role.ADMIN,
        )
        self.lead = _make_lead(default_test_company(), self.user, "Call Lead")
        self.other_lead = _make_lead(default_test_company(), self.user, "Other Lead")
        self.account = _make_account(default_test_company(), self.user, "Call Account")
        self.contact = _make_contact(
            default_test_company(), self.user, "Call Contact", account=self.account,
        )
        self.other_contact = _make_contact(
            default_test_company(), self.user, "Other Contact",
        )
        self.now = timezone.now()
        self.client.force_authenticate(self.user)

    # ---------- helpers ----------

    def _payload(self, **overrides):
        payload = {
            "outcome": "Connected",
            "call_start_time": (self.now - timedelta(hours=1)).isoformat(),
            "duration_seconds": 125,
            "description": "Discussed pricing.",
        }
        payload.update(overrides)
        return payload

    def _create(self, **overrides):
        return self.client.post("/api/calls/", self._payload(**overrides), format="json")

    def _create_ok(self, **overrides):
        response = self._create(**overrides)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data

    def _list(self, field=None, value=None, **params):
        query = dict(params)
        if field is not None:
            query["filters"] = _filters(field, value)
        return self.client.get("/api/calls/", query)

    def _ids(self, response):
        return [row["id"] for row in response.data["results"]]

    def _timeline(self, kind, entity_id):
        return self.client.get(f"/api/timeline/{kind}/{entity_id}/")

    def _event_types(self, response):
        return [event["event_type"] for event in response.data]


class CallAuthenticationTests(CallApiTestCase):
    def test_calls_require_authentication(self):
        self.client.force_authenticate(None)
        call = self._make_call_row()
        call_url = f"/api/calls/{call.id}/"

        responses = [
            self.client.get("/api/calls/"),
            self.client.post("/api/calls/", self._payload(lead_id=str(self.lead.id)), format="json"),
            self.client.get(call_url),
            self.client.patch(call_url, {"description": "x"}, format="json"),
            self.client.delete(call_url),
            self.client.get(f"/api/timeline/calls/{call.id}/"),
        ]

        for response in responses:
            self.assertIn(
                response.status_code,
                {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN},
            )

        call.refresh_from_db()
        self.assertFalse(call.is_deleted)
        self.assertEqual(DjangoCallModel.objects.count(), 1)

    def _make_call_row(self):
        return DjangoCallModel.objects.create(
            company=default_test_company(),
            lead=self.lead,
            owner=self.user,
            created_by=self.user,
            outcome="Connected",
            call_start_time=self.now - timedelta(hours=2),
        )


class LeadCallFlowTests(CallApiTestCase):
    def test_three_calls_on_one_lead_are_listed_newest_first(self):
        # Created out of chronological order on purpose: the list must be
        # ordered by call_start_time, not by creation time.
        starts = {
            "middle": self.now - timedelta(hours=2),
            "oldest": self.now - timedelta(hours=3),
            "newest": self.now - timedelta(hours=1),
        }
        created = {}
        snapshots = []

        for label, start in starts.items():
            created[label] = self._create_ok(
                lead_id=str(self.lead.id),
                call_start_time=start.isoformat(),
                description=f"{label} call",
            )

            # Logging a new call never modifies the calls logged before it.
            current = {
                row.id: (row.description, row.duration_seconds, row.outcome,
                         row.call_start_time, row.updated_at)
                for row in DjangoCallModel.objects.all()
            }
            snapshots.append(current)
            if len(snapshots) > 1:
                for call_id, values in snapshots[-2].items():
                    self.assertEqual(snapshots[-1][call_id], values)

        for sort_params in (
            {"sort_by": "call_start_time", "sort_direction": "desc", "page_size": 50},
            {},
        ):
            response = self._list("lead_id", self.lead.id, **sort_params)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(
                self._ids(response),
                [created["newest"]["id"], created["middle"]["id"], created["oldest"]["id"]],
            )
            self.assertEqual(response.data["pagination"]["total"], 3)

        ascending = self._list(
            "lead_id", self.lead.id,
            sort_by="call_start_time", sort_direction="asc",
        )
        self.assertEqual(
            self._ids(ascending),
            [created["oldest"]["id"], created["middle"]["id"], created["newest"]["id"]],
        )

    def test_list_rows_expose_names_and_no_history(self):
        created = self._create_ok(lead_id=str(self.lead.id), duration_seconds=250)

        response = self._list("lead_id", self.lead.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data["results"][0]
        self.assertEqual(
            set(row),
            {
                "id", "lead_id", "lead_name", "contact_id", "contact_name",
                "account_id", "account_name", "owner_id", "owner_name",
                "call_type", "outcome", "call_start_time", "duration_seconds",
                "duration_label", "description", "entry_method", "created_by_id",
                "created_at", "updated_at",
            },
        )
        self.assertEqual(row["id"], created["id"])
        self.assertEqual(row["lead_id"], str(self.lead.id))
        self.assertEqual(row["lead_name"], "Call Lead")
        self.assertIsNone(row["contact_id"])
        self.assertIsNone(row["contact_name"])
        self.assertIsNone(row["account_name"])
        self.assertEqual(row["owner_id"], str(self.user.id))
        self.assertEqual(row["owner_name"], "Call Owner")
        self.assertEqual(row["call_type"], "Outbound")
        self.assertEqual(row["duration_label"], "4 min 10 sec")
        self.assertEqual(row["created_by_id"], str(self.user.id))
        self.assertNotIn("change_history", row)
        self.assertNotIn("related_calls", row)

    def test_create_response_shape(self):
        data = self._create_ok(lead_id=str(self.lead.id), duration_seconds=3725)

        self.assertEqual(
            set(data),
            {
                "id", "lead_id", "contact_id", "account_id", "owner_id",
                "call_type", "outcome", "call_start_time", "duration_seconds",
                "duration_label", "description", "entry_method", "created_by_id",
                "created_at", "updated_at",
            },
        )
        self.assertEqual(data["lead_id"], str(self.lead.id))
        self.assertEqual(data["owner_id"], str(self.user.id))
        self.assertEqual(data["call_type"], "Outbound")
        self.assertEqual(data["entry_method"], "MANUAL")
        self.assertEqual(data["duration_label"], "1 hr 2 min 5 sec")

    def test_defaults_when_optional_fields_are_omitted(self):
        data = self._create_ok(
            lead_id=str(self.lead.id),
            description=None,
        )
        payload = {
            "lead_id": str(self.lead.id),
            "outcome": "Busy",
            "call_start_time": (self.now - timedelta(minutes=30)).isoformat(),
        }
        response = self.client.post("/api/calls/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["call_type"], "Outbound")
        self.assertEqual(response.data["entry_method"], "MANUAL")
        self.assertEqual(response.data["duration_seconds"], 0)
        self.assertIsNone(response.data["description"])
        self.assertIsNone(data["description"])

    def test_pagination_shape(self):
        for index in range(3):
            self._create_ok(
                lead_id=str(self.lead.id),
                call_start_time=(self.now - timedelta(hours=index + 1)).isoformat(),
            )

        response = self._list("lead_id", self.lead.id, page_size=2, page=2)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["pagination"],
            {"page": 2, "page_size": 2, "total": 3, "total_pages": 2},
        )
        self.assertEqual(len(response.data["results"]), 1)

    def test_invalid_list_query_returns_400(self):
        response = self.client.get("/api/calls/", {"filters": "not-json"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

        response = self.client.get("/api/calls/", {"sort_by": "nonsense"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self._list("not_a_field", "x")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ContactCallFlowTests(CallApiTestCase):
    def test_contact_calls_with_and_without_account(self):
        with_account = self._create_ok(
            contact_id=str(self.contact.id),
            account_id=str(self.account.id),
            call_start_time=(self.now - timedelta(hours=2)).isoformat(),
        )
        without_account = self._create_ok(
            contact_id=str(self.contact.id),
            call_start_time=(self.now - timedelta(hours=1)).isoformat(),
        )
        lead_call = self._create_ok(lead_id=str(self.lead.id))
        other_contact_call = self._create_ok(contact_id=str(self.other_contact.id))

        response = self._list(
            "contact_id", self.contact.id,
            sort_by="call_start_time", sort_direction="desc", page_size=50,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(response), [without_account["id"], with_account["id"]])
        self.assertNotIn(lead_call["id"], self._ids(response))
        self.assertNotIn(other_contact_call["id"], self._ids(response))

        rows = {row["id"]: row for row in response.data["results"]}
        self.assertEqual(rows[with_account["id"]]["account_id"], str(self.account.id))
        self.assertEqual(rows[with_account["id"]]["account_name"], "Call Account")
        self.assertEqual(rows[with_account["id"]]["contact_name"], "Call Contact")
        self.assertIsNone(rows[with_account["id"]]["lead_id"])
        self.assertIsNone(rows[without_account["id"]]["account_id"])
        self.assertIsNone(rows[without_account["id"]]["account_name"])

        lead_response = self._list("lead_id", self.lead.id)
        self.assertEqual(self._ids(lead_response), [lead_call["id"]])


class EntryMethodTests(CallApiTestCase):
    def test_manual_and_timer_entries_persist(self):
        manual = self._create_ok(
            lead_id=str(self.lead.id),
            entry_method="MANUAL",
            duration_seconds=12 * 60,
        )
        timer = self._create_ok(
            contact_id=str(self.contact.id),
            entry_method="TIMER",
            duration_seconds=95,
        )

        manual_row = DjangoCallModel.objects.get(id=manual["id"])
        timer_row = DjangoCallModel.objects.get(id=timer["id"])

        self.assertEqual(manual_row.entry_method, "MANUAL")
        self.assertEqual(manual_row.duration_seconds, 720)
        self.assertEqual(timer_row.entry_method, "TIMER")
        self.assertEqual(timer_row.duration_seconds, 95)

        manual_detail = self.client.get(f"/api/calls/{manual['id']}/")
        timer_detail = self.client.get(f"/api/calls/{timer['id']}/")

        self.assertEqual(manual_detail.data["entry_method"], "MANUAL")
        self.assertEqual(manual_detail.data["duration_label"], "12 min 0 sec")
        self.assertEqual(timer_detail.data["entry_method"], "TIMER")
        self.assertEqual(timer_detail.data["duration_label"], "1 min 35 sec")

    def test_invalid_entry_method_is_rejected(self):
        response = self._create(lead_id=str(self.lead.id), entry_method="VOICE")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CallValidationTests(CallApiTestCase):
    def test_invalid_creates_are_rejected_and_nothing_is_written(self):
        deleted_lead = _make_lead(default_test_company(), self.user, "Deleted Lead")
        deleted_lead.is_deleted = True
        deleted_lead.save()
        deleted_contact = _make_contact(default_test_company(), self.user, "Deleted Contact")
        deleted_contact.is_deleted = True
        deleted_contact.save()
        deleted_account = _make_account(default_test_company(), self.user, "Deleted Account")
        deleted_account.is_deleted = True
        deleted_account.save()

        too_far = (timezone.now() + timedelta(minutes=10)).isoformat()

        cases = {
            "neither lead nor contact": {},
            "both lead and contact": {
                "lead_id": str(self.lead.id),
                "contact_id": str(self.contact.id),
            },
            "account without contact": {
                "lead_id": str(self.lead.id),
                "account_id": str(self.account.id),
            },
            "account only": {"account_id": str(self.account.id)},
            "negative duration": {"lead_id": str(self.lead.id), "duration_seconds": -1},
            "duration above 24h": {"lead_id": str(self.lead.id), "duration_seconds": 86401},
            "non integer duration": {"lead_id": str(self.lead.id), "duration_seconds": "abc"},
            "start time in the future": {
                "lead_id": str(self.lead.id),
                "call_start_time": too_far,
            },
            "description too long": {
                "lead_id": str(self.lead.id),
                "description": "x" * 1001,
            },
            "deleted lead": {"lead_id": str(deleted_lead.id)},
            "deleted contact": {"contact_id": str(deleted_contact.id)},
            "deleted account": {
                "contact_id": str(self.contact.id),
                "account_id": str(deleted_account.id),
            },
            "unknown lead": {"lead_id": str(uuid.uuid4())},
            "unknown contact": {"contact_id": str(uuid.uuid4())},
            "invalid outcome": {"lead_id": str(self.lead.id), "outcome": "Maybe"},
            "invalid call type": {"lead_id": str(self.lead.id), "call_type": "Sideways"},
        }

        for label, overrides in cases.items():
            with self.subTest(label):
                response = self._create(**overrides)

                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST, response.data,
                )

        self.assertEqual(DjangoCallModel.objects.count(), 0)
        self.assertEqual(TimelineEvent.objects.filter(event_type="CALL_LOGGED").count(), 0)

    def test_missing_required_fields_are_rejected(self):
        for missing in ("outcome", "call_start_time"):
            with self.subTest(missing):
                payload = self._payload(lead_id=str(self.lead.id))
                payload.pop(missing)

                response = self.client.post("/api/calls/", payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_boundary_values_are_accepted(self):
        accepted = [
            {"duration_seconds": 0},
            {"duration_seconds": 86400},
            {"description": "x" * 1000},
            {"description": ""},
            {"call_start_time": (timezone.now() + timedelta(minutes=1)).isoformat()},
            {"call_type": "Inbound"},
            {"outcome": "Callback Requested"},
        ]

        for overrides in accepted:
            with self.subTest(overrides=list(overrides)):
                response = self._create(lead_id=str(self.lead.id), **overrides)

                self.assertEqual(
                    response.status_code, status.HTTP_201_CREATED, response.data,
                )

    def test_owner_defaults_to_request_user_and_can_be_overridden(self):
        default = self._create_ok(lead_id=str(self.lead.id))
        self.assertEqual(default["owner_id"], str(self.user.id))

        other_admin = make_user(default_test_company(), User.Role.ADMIN, "other-admin@example.com")
        explicit = self._create_ok(lead_id=str(self.lead.id), owner_id=str(other_admin.id))
        self.assertEqual(explicit["owner_id"], str(other_admin.id))
        self.assertEqual(explicit["created_by_id"], str(self.user.id))

        sales = make_user(
            default_test_company(), User.Role.SALES_EXECUTIVE, "sales-exec@example.com",
        )
        response = self._create(lead_id=str(self.lead.id), owner_id=str(sales.id))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CallDetailTests(CallApiTestCase):
    def _lead_calls(self):
        oldest = self._create_ok(
            lead_id=str(self.lead.id),
            call_start_time=(self.now - timedelta(hours=3)).isoformat(),
            description="oldest",
        )
        middle = self._create_ok(
            lead_id=str(self.lead.id),
            call_start_time=(self.now - timedelta(hours=2)).isoformat(),
            description="middle",
        )
        newest = self._create_ok(
            lead_id=str(self.lead.id),
            call_start_time=(self.now - timedelta(hours=1)).isoformat(),
            description="newest",
        )
        return oldest, middle, newest

    def test_lead_call_detail_has_history_and_related_calls(self):
        oldest, middle, newest = self._lead_calls()
        # A contact call must never be mixed into the lead's related calls.
        self._create_ok(contact_id=str(self.contact.id))

        response = self.client.get(f"/api/calls/{middle['id']}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        self.assertEqual(data["id"], middle["id"])
        self.assertEqual(data["lead_name"], "Call Lead")
        self.assertEqual(data["description"], "middle")
        self.assertEqual(
            data["related_record"],
            {"type": "LEAD", "id": str(self.lead.id), "name": "Call Lead"},
        )

        self.assertEqual(len(data["change_history"]), 1)
        logged = data["change_history"][0]
        self.assertEqual(logged["event_type"], "CALL_LOGGED")
        self.assertEqual(logged["actor"], {"id": str(self.user.id), "name": "Call Owner"})
        self.assertEqual(logged["changes"], {})
        self.assertIn("Call logged", logged["message"])
        self.assertEqual(
            set(logged),
            {"id", "event_type", "actor", "message", "changes", "created_at"},
        )

        # Newest first, excluding the call itself.
        self.assertEqual(
            [item["id"] for item in data["related_calls"]],
            [newest["id"], oldest["id"]],
        )
        self.assertEqual(
            set(data["related_calls"][0]),
            {
                "id", "call_start_time", "duration_seconds", "duration_label",
                "outcome", "call_type", "description", "owner_name",
            },
        )
        self.assertEqual(data["related_calls"][0]["owner_name"], "Call Owner")
        self.assertEqual(data["total_calls_for_record"], 3)

    def test_contact_call_detail_has_history_and_related_calls(self):
        first = self._create_ok(
            contact_id=str(self.contact.id),
            account_id=str(self.account.id),
            call_start_time=(self.now - timedelta(hours=2)).isoformat(),
        )
        second = self._create_ok(
            contact_id=str(self.contact.id),
            call_start_time=(self.now - timedelta(hours=1)).isoformat(),
        )
        self._create_ok(lead_id=str(self.lead.id))
        self._create_ok(contact_id=str(self.other_contact.id))

        response = self.client.get(f"/api/calls/{first['id']}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(
            data["related_record"],
            {"type": "CONTACT", "id": str(self.contact.id), "name": "Call Contact"},
        )
        self.assertEqual(data["account_name"], "Call Account")
        self.assertEqual(data["change_history"][0]["event_type"], "CALL_LOGGED")
        self.assertEqual([item["id"] for item in data["related_calls"]], [second["id"]])
        self.assertEqual(data["total_calls_for_record"], 2)

    def test_only_call_has_no_related_calls(self):
        only = self._create_ok(lead_id=str(self.lead.id))

        data = self.client.get(f"/api/calls/{only['id']}/").data

        self.assertEqual(data["related_calls"], [])
        self.assertEqual(data["total_calls_for_record"], 1)

    def test_related_calls_are_capped_at_fifty(self):
        base = self.now - timedelta(days=1)
        DjangoCallModel.objects.bulk_create([
            DjangoCallModel(
                company=default_test_company(),
                lead=self.lead,
                owner=self.user,
                created_by=self.user,
                outcome="Connected",
                call_start_time=base + timedelta(minutes=index),
            )
            for index in range(53)
        ])
        target = DjangoCallModel.objects.filter(lead=self.lead).first()

        data = self.client.get(f"/api/calls/{target.id}/").data

        self.assertEqual(len(data["related_calls"]), 50)
        self.assertEqual(data["total_calls_for_record"], 53)

    def test_unknown_call_returns_404(self):
        response = self.client.get(f"/api/calls/{uuid.uuid4()}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {"detail": "Call not found."})

    def test_detail_shows_updated_event_with_old_and_new_values(self):
        call = self._create_ok(
            lead_id=str(self.lead.id),
            description="before",
            duration_seconds=60,
        )

        patch = self.client.patch(
            f"/api/calls/{call['id']}/",
            {"description": "after", "duration_seconds": 180},
            format="json",
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK, patch.data)

        data = self.client.get(f"/api/calls/{call['id']}/").data

        self.assertEqual(data["description"], "after")
        self.assertEqual(data["duration_seconds"], 180)
        self.assertEqual(data["duration_label"], "3 min 0 sec")
        self.assertEqual(
            [event["event_type"] for event in data["change_history"]],
            ["CALL_UPDATED", "CALL_LOGGED"],
        )
        updated = data["change_history"][0]
        self.assertEqual(
            updated["changes"],
            {
                "description": {"old_value": "before", "new_value": "after"},
                "duration_seconds": {"old_value": 60, "new_value": 180},
            },
        )
        self.assertEqual(updated["actor"]["id"], str(self.user.id))
        self.assertEqual(data["change_history"][1]["changes"], {})


class CallUpdateTests(CallApiTestCase):
    def test_patch_changes_fields_and_writes_updated_event(self):
        call = self._create_ok(
            lead_id=str(self.lead.id),
            outcome="Busy",
            call_type="Outbound",
            description="before",
            duration_seconds=60,
        )
        new_start = (self.now - timedelta(hours=5)).isoformat()

        response = self.client.patch(
            f"/api/calls/{call['id']}/",
            {
                "description": "after",
                "duration_seconds": 300,
                "outcome": "Connected",
                "call_type": "Inbound",
                "call_start_time": new_start,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["id"], call["id"])
        self.assertEqual(response.data["description"], "after")
        self.assertEqual(response.data["duration_seconds"], 300)
        self.assertEqual(response.data["outcome"], "Connected")
        self.assertEqual(response.data["call_type"], "Inbound")
        # Immutable fields are unchanged.
        self.assertEqual(response.data["lead_id"], str(self.lead.id))
        self.assertEqual(response.data["entry_method"], "MANUAL")

        row = DjangoCallModel.objects.get(id=call["id"])
        self.assertEqual(row.description, "after")
        self.assertEqual(row.duration_seconds, 300)
        self.assertEqual(row.outcome, "Connected")
        self.assertEqual(row.call_type, "Inbound")

        events = TimelineEvent.objects.filter(event_type="CALL_UPDATED")
        self.assertEqual(events.count(), 1)
        changes = events.get().metadata["changes"]
        self.assertEqual(
            set(changes),
            {"description", "duration_seconds", "outcome", "call_type", "call_start_time"},
        )
        self.assertEqual(changes["outcome"], {"old_value": "Busy", "new_value": "Connected"})
        self.assertEqual(changes["call_type"], {"old_value": "Outbound", "new_value": "Inbound"})
        self.assertEqual(changes["duration_seconds"], {"old_value": 60, "new_value": 300})

        lead_timeline = self._timeline("leads", self.lead.id)
        self.assertIn("CALL_UPDATED", self._event_types(lead_timeline))

    def test_patch_can_clear_description(self):
        call = self._create_ok(lead_id=str(self.lead.id), description="something")

        response = self.client.patch(
            f"/api/calls/{call['id']}/", {"description": ""}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIsNone(response.data["description"])
        changes = TimelineEvent.objects.get(event_type="CALL_UPDATED").metadata["changes"]
        self.assertEqual(
            changes["description"], {"old_value": "something", "new_value": None},
        )

    def test_noop_patches_write_no_event(self):
        call = self._create_ok(
            lead_id=str(self.lead.id),
            description="same",
            duration_seconds=90,
        )
        row = DjangoCallModel.objects.get(id=call["id"])
        same_instant_other_offset = (
            row.call_start_time.astimezone(ZoneInfo("Asia/Kolkata")).isoformat()
        )

        noops = [
            {},
            {"description": "same"},
            {"duration_seconds": 90},
            {"outcome": "Connected", "call_type": "Outbound"},
            {"call_start_time": same_instant_other_offset},
            {"description": "same", "duration_seconds": 90, "call_start_time": same_instant_other_offset},
        ]

        for body in noops:
            with self.subTest(body=body):
                response = self.client.patch(
                    f"/api/calls/{call['id']}/", body, format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        self.assertEqual(TimelineEvent.objects.filter(event_type="CALL_UPDATED").count(), 0)

    def test_patch_rejects_immutable_and_unknown_fields(self):
        call = self._create_ok(contact_id=str(self.contact.id), description="keep")
        other_admin = make_user(default_test_company(), User.Role.ADMIN, "another-admin@example.com")

        forbidden = {
            "lead_id": str(self.lead.id),
            "contact_id": str(self.other_contact.id),
            "account_id": str(self.account.id),
            "owner_id": str(other_admin.id),
            "entry_method": "TIMER",
            "created_by_id": str(other_admin.id),
            "is_deleted": True,
            "unknown_field": "x",
        }

        for field, value in forbidden.items():
            with self.subTest(field):
                response = self.client.patch(
                    f"/api/calls/{call['id']}/",
                    {"description": "changed", field: value},
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

        row = DjangoCallModel.objects.get(id=call["id"])
        self.assertEqual(row.description, "keep")
        self.assertEqual(row.contact_id, self.contact.id)
        self.assertIsNone(row.lead_id)
        self.assertEqual(row.owner_id, self.user.id)
        self.assertEqual(row.entry_method, "MANUAL")
        self.assertFalse(row.is_deleted)
        self.assertEqual(TimelineEvent.objects.filter(event_type="CALL_UPDATED").count(), 0)

    def test_patch_rejects_invalid_values(self):
        call = self._create_ok(lead_id=str(self.lead.id), duration_seconds=60)

        invalid = [
            {"duration_seconds": -1},
            {"duration_seconds": 86401},
            {"description": "x" * 1001},
            {"outcome": "Maybe"},
            {"call_type": "Sideways"},
            {"call_start_time": (timezone.now() + timedelta(minutes=10)).isoformat()},
            {"call_start_time": "not-a-date"},
        ]

        for body in invalid:
            with self.subTest(body=body):
                response = self.client.patch(
                    f"/api/calls/{call['id']}/", body, format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(DjangoCallModel.objects.get(id=call["id"]).duration_seconds, 60)
        self.assertEqual(TimelineEvent.objects.filter(event_type="CALL_UPDATED").count(), 0)

    def test_only_the_latest_call_can_be_updated(self):
        older = self._create_ok(
            lead_id=str(self.lead.id),
            call_start_time=(self.now - timedelta(hours=3)).isoformat(),
            description="older",
        )
        latest = self._create_ok(
            lead_id=str(self.lead.id),
            call_start_time=(self.now - timedelta(hours=1)).isoformat(),
            description="latest",
        )

        response = self.client.patch(
            f"/api/calls/{older['id']}/", {"description": "edited"}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Only the latest call", response.data["detail"])
        self.assertEqual(DjangoCallModel.objects.get(id=older["id"]).description, "older")
        self.assertEqual(TimelineEvent.objects.filter(event_type="CALL_UPDATED").count(), 0)

        response = self.client.patch(
            f"/api/calls/{latest['id']}/", {"description": "edited"}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(DjangoCallModel.objects.get(id=latest["id"]).description, "edited")

    def test_detail_exposes_is_latest_flag(self):
        older = self._create_ok(
            contact_id=str(self.contact.id),
            call_start_time=(self.now - timedelta(hours=3)).isoformat(),
        )
        latest = self._create_ok(
            contact_id=str(self.contact.id),
            call_start_time=(self.now - timedelta(hours=1)).isoformat(),
        )

        self.assertFalse(self.client.get(f"/api/calls/{older['id']}/").data["is_latest"])
        self.assertTrue(self.client.get(f"/api/calls/{latest['id']}/").data["is_latest"])

    def test_patch_unknown_call_returns_404(self):
        response = self.client.patch(
            f"/api/calls/{uuid.uuid4()}/", {"description": "x"}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {"detail": "Call not found."})


class CallDeleteTests(CallApiTestCase):
    def test_delete_soft_deletes_and_writes_deleted_event(self):
        keep = self._create_ok(lead_id=str(self.lead.id), description="keep")
        call = self._create_ok(lead_id=str(self.lead.id), description="remove")

        response = self.client.delete(f"/api/calls/{call['id']}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"message": "Call deleted successfully."})

        row = DjangoCallModel.objects.get(id=call["id"])
        self.assertTrue(row.is_deleted)
        self.assertFalse(DjangoCallModel.objects.get(id=keep["id"]).is_deleted)

        deleted_events = TimelineEvent.objects.filter(event_type="CALL_DELETED")
        self.assertEqual(deleted_events.count(), 1)
        self.assertEqual(deleted_events.get().metadata["call_id"], call["id"])

        # The record's own timeline reports the deletion.
        self.assertIn("CALL_DELETED", self._event_types(self._timeline("leads", self.lead.id)))

        listing = self._list("lead_id", self.lead.id)
        self.assertEqual(self._ids(listing), [keep["id"]])
        self.assertEqual(listing.data["pagination"]["total"], 1)

        self.assertEqual(
            self.client.get(f"/api/calls/{call['id']}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/calls/{call['id']}/", {"description": "x"}, format="json",
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        again = self.client.delete(f"/api/calls/{call['id']}/")
        self.assertEqual(again.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(again.data, {"detail": "Call not found."})
        self.assertEqual(TimelineEvent.objects.filter(event_type="CALL_DELETED").count(), 1)

        self.assertEqual(
            self._timeline("calls", call["id"]).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_deleted_call_is_excluded_from_related_calls_and_totals(self):
        first = self._create_ok(lead_id=str(self.lead.id))
        second = self._create_ok(lead_id=str(self.lead.id))
        self.client.delete(f"/api/calls/{second['id']}/")

        data = self.client.get(f"/api/calls/{first['id']}/").data

        self.assertEqual(data["related_calls"], [])
        self.assertEqual(data["total_calls_for_record"], 1)

    def test_delete_unknown_call_returns_404(self):
        response = self.client.delete(f"/api/calls/{uuid.uuid4()}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {"detail": "Call not found."})


class CallTimelineTests(CallApiTestCase):
    def test_call_logged_appears_on_lead_contact_and_call_timelines(self):
        lead_call = self._create_ok(lead_id=str(self.lead.id))
        contact_call = self._create_ok(
            contact_id=str(self.contact.id),
            account_id=str(self.account.id),
        )

        lead_timeline = self._timeline("leads", self.lead.id)
        self.assertEqual(lead_timeline.status_code, status.HTTP_200_OK)
        self.assertEqual(self._event_types(lead_timeline), ["CALL_LOGGED"])
        self.assertEqual(
            lead_timeline.data[0]["metadata"]["call_id"], lead_call["id"],
        )

        contact_timeline = self._timeline("contacts", self.contact.id)
        self.assertEqual(contact_timeline.status_code, status.HTTP_200_OK)
        self.assertEqual(self._event_types(contact_timeline), ["CALL_LOGGED"])
        self.assertEqual(
            contact_timeline.data[0]["metadata"]["call_id"], contact_call["id"],
        )

        account_timeline = self._timeline("accounts", self.account.id)
        self.assertIn("CALL_LOGGED", self._event_types(account_timeline))

        for call in (lead_call, contact_call):
            call_timeline = self._timeline("calls", call["id"])
            self.assertEqual(call_timeline.status_code, status.HTTP_200_OK)
            self.assertEqual(self._event_types(call_timeline), ["CALL_LOGGED"])
            self.assertEqual(
                call_timeline.data[0]["actor"]["id"], str(self.user.id),
            )

        other_lead_timeline = self._timeline("leads", self.other_lead.id)
        self.assertEqual(other_lead_timeline.data, [])

    def test_unknown_call_timeline_returns_404(self):
        response = self._timeline("calls", uuid.uuid4())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CallDeleteCascadeTests(CallApiTestCase):
    def _event_ids_for_call(self, call_id):
        return list(
            TimelineEventTarget.objects.filter(
                entity_type="CALL", entity_id=call_id,
            ).values_list("event_id", flat=True)
        )

    def _assert_call_gone(self, call_id):
        self.assertTrue(DjangoCallModel.objects.get(id=call_id).is_deleted)
        self.assertEqual(
            self.client.get(f"/api/calls/{call_id}/").status_code, status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/calls/{call_id}/", {"description": "x"}, format="json",
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.delete(f"/api/calls/{call_id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self._timeline("calls", call_id).status_code, status.HTTP_404_NOT_FOUND,
        )
        self.assertFalse(
            TimelineEventTarget.objects.filter(
                entity_type="CALL", entity_id=call_id, is_deleted=False,
            ).exists()
        )

    def test_deleting_a_lead_soft_deletes_its_calls_and_timeline_events(self):
        lead_calls = [
            self._create_ok(lead_id=str(self.lead.id), description=f"lead call {i}")
            for i in range(3)
        ]
        survivor = self._create_ok(lead_id=str(self.other_lead.id))
        contact_call = self._create_ok(contact_id=str(self.contact.id))
        event_ids = {
            call["id"]: self._event_ids_for_call(call["id"]) for call in lead_calls
        }
        survivor_event_ids = self._event_ids_for_call(survivor["id"])
        self.assertTrue(all(event_ids.values()))

        response = self.client.delete(f"/api/leads/{self.lead.id}/delete/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for call in lead_calls:
            self._assert_call_gone(call["id"])
            self.assertEqual(
                set(TimelineEvent.objects.filter(
                    id__in=event_ids[call["id"]],
                ).values_list("is_deleted", flat=True)),
                {True},
            )

        # Gone from every list, whatever the filter.
        self.assertEqual(self._list("lead_id", self.lead.id).data["results"], [])
        everything = self._ids(self._list(page_size=100))
        self.assertEqual(set(everything), {survivor["id"], contact_call["id"]})

        # Other records' calls are untouched, including their history.
        self.assertFalse(DjangoCallModel.objects.get(id=survivor["id"]).is_deleted)
        self.assertFalse(DjangoCallModel.objects.get(id=contact_call["id"]).is_deleted)
        self.assertFalse(
            TimelineEvent.objects.filter(id__in=survivor_event_ids, is_deleted=True).exists()
        )
        self.assertEqual(
            self._event_types(self._timeline("calls", survivor["id"])), ["CALL_LOGGED"],
        )
        self.assertEqual(
            self.client.get(f"/api/calls/{survivor['id']}/").status_code,
            status.HTTP_200_OK,
        )

    def test_deleting_a_contact_soft_deletes_its_calls_and_timeline_events(self):
        no_account = self._create_ok(contact_id=str(self.contact.id))
        with_account = self._create_ok(
            contact_id=str(self.contact.id), account_id=str(self.account.id),
        )
        survivor = self._create_ok(contact_id=str(self.other_contact.id))
        lead_call = self._create_ok(lead_id=str(self.lead.id))
        no_account_events = self._event_ids_for_call(no_account["id"])

        response = self.client.delete(f"/api/contacts/{self.contact.id}/delete/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for call in (no_account, with_account):
            self._assert_call_gone(call["id"])

        self.assertEqual(
            set(TimelineEvent.objects.filter(
                id__in=no_account_events,
            ).values_list("is_deleted", flat=True)),
            {True},
        )
        self.assertEqual(self._list("contact_id", self.contact.id).data["results"], [])
        self.assertEqual(
            set(self._ids(self._list(page_size=100))),
            {survivor["id"], lead_call["id"]},
        )
        for untouched in (survivor, lead_call):
            self.assertEqual(
                self.client.get(f"/api/calls/{untouched['id']}/").status_code,
                status.HTTP_200_OK,
            )
            self.assertEqual(
                self._event_types(self._timeline("calls", untouched["id"])),
                ["CALL_LOGGED"],
            )

    def test_deleting_an_account_keeps_contact_calls_and_unlinks_the_account(self):
        call = self._create_ok(
            contact_id=str(self.contact.id), account_id=str(self.account.id),
        )

        response = self.client.delete(f"/api/accounts/{self.account.id}/delete/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        row = DjangoCallModel.objects.get(id=call["id"])
        self.assertFalse(row.is_deleted)
        self.assertIsNone(row.account_id)
        self.assertEqual(row.contact_id, self.contact.id)

        detail = self.client.get(f"/api/calls/{call['id']}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertIsNone(detail.data["account_id"])
        self.assertIsNone(detail.data["account_name"])
        self.assertEqual(detail.data["related_record"]["type"], "CONTACT")
        self.assertEqual(self._ids(self._list("contact_id", self.contact.id)), [call["id"]])
        self.assertEqual(
            self._event_types(self._timeline("contacts", self.contact.id)), ["CALL_LOGGED"],
        )
        self.assertEqual(
            self._event_types(self._timeline("calls", call["id"])), ["CALL_LOGGED"],
        )

    def test_account_delete_soft_deletes_returned_calls_and_their_timeline(self):
        # The DB constraints make account-only calls impossible, so the
        # use case is exercised with a fake repository (like tasks, the
        # repository decides which calls are returned).
        call_ids = [uuid.uuid4(), uuid.uuid4()]
        account = Mock(is_deleted=False, id=uuid.uuid4())
        account_repository = Mock()
        account_repository.get_by_id.return_value = account
        call_repository = Mock()
        call_repository.soft_delete_by_account_id.return_value = call_ids
        timeline_repository = Mock()
        transaction_manager = Mock()
        transaction_manager.execute.side_effect = lambda operation: operation()

        DeleteAccountUseCase(
            account_repository,
            Mock(),
            Mock(),
            call_repository,
            timeline_repository,
            transaction_manager,
        ).execute(DeleteAccountDTO(account_id=account.id), uuid.uuid4())

        call_repository.soft_delete_by_account_id.assert_called_once_with(account.id)
        call_repository.unlink_account_from_contact_calls.assert_called_once_with(account.id)
        timeline_calls = [
            call.args for call in timeline_repository.soft_delete_by_entity.call_args_list
        ]
        self.assertEqual(
            timeline_calls,
            [("CALL", call_ids[0]), ("CALL", call_ids[1]), ("ACCOUNT", account.id)],
        )

    def test_converted_lead_keeps_its_calls_visible(self):
        first = self._create_ok(lead_id=str(self.lead.id))
        second = self._create_ok(lead_id=str(self.lead.id))

        # Conversion only flags the lead (ConvertLeadUseCase neither deletes
        # the lead nor touches calls), so it is simulated with the flag.
        DjangoLeadModel.objects.filter(id=self.lead.id).update(is_converted=True)

        listing = self._list("lead_id", self.lead.id)
        self.assertEqual(self._ids(listing), [second["id"], first["id"]])

        detail = self.client.get(f"/api/calls/{first['id']}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["related_record"]["type"], "LEAD")
        self.assertEqual(detail.data["total_calls_for_record"], 2)
        self.assertEqual(
            self._event_types(self._timeline("calls", first["id"])), ["CALL_LOGGED"],
        )
        self.assertFalse(DjangoCallModel.objects.filter(lead=self.lead, is_deleted=True).exists())

    def test_calls_of_another_company_survive_a_lead_delete(self):
        company_b = make_company("Company B", "company-b-calls")
        admin_b = make_user(company_b, User.Role.ADMIN, "admin-b-calls@example.com")
        lead_b = _make_lead(company_b, admin_b, "Lead B")
        call_b = DjangoCallModel.objects.create(
            company=company_b,
            lead=lead_b,
            owner=admin_b,
            created_by=admin_b,
            outcome="Connected",
            call_start_time=self.now - timedelta(hours=1),
        )
        self._create_ok(lead_id=str(self.lead.id))

        response = self.client.delete(f"/api/leads/{self.lead.id}/delete/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        call_b.refresh_from_db()
        self.assertFalse(call_b.is_deleted)

    def test_lead_delete_rolls_back_calls_when_timeline_cascade_fails(self):
        call = self._create_ok(lead_id=str(self.lead.id))

        class FailingTimelineRepository:
            def soft_delete_by_entity(self, entity_type, entity_id):
                raise RuntimeError("timeline cascade failed")

        company_id = default_test_company().id
        use_case = DeleteLeadUseCase(
            DjangoLeadRepository(company_id=company_id),
            DjangoTaskRepository(company_id=company_id),
            DjangoCallRepository(company_id=company_id),
            FailingTimelineRepository(),
            DjangoTransactionManager(),
        )

        with self.assertRaises(RuntimeError):
            use_case.execute(self.lead.id)

        self.lead.refresh_from_db()
        self.assertFalse(self.lead.is_deleted)
        self.assertFalse(DjangoCallModel.objects.get(id=call["id"]).is_deleted)
        self.assertEqual(
            self.client.get(f"/api/calls/{call['id']}/").status_code, status.HTTP_200_OK,
        )

    def test_contact_delete_use_case_passes_every_deleted_call_to_timeline(self):
        from src.modules.contacts.application.dto.delete_contact import DeleteContactDTO
        from src.modules.contacts.application.use_cases.delete_contact import (
            DeleteContactUseCase,
        )

        call_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        contact_repository = Mock()
        contact_repository.get_by_id.return_value = Mock(is_deleted=False)
        call_repository = Mock()
        call_repository.soft_delete_by_contact_id.return_value = call_ids
        timeline_repository = Mock()
        transaction_manager = Mock()
        transaction_manager.execute.side_effect = lambda operation: operation()
        contact_id = uuid.uuid4()

        DeleteContactUseCase(
            contact_repository,
            Mock(),
            call_repository,
            timeline_repository,
            transaction_manager,
        ).execute(DeleteContactDTO(contact_id=contact_id))

        call_repository.soft_delete_by_contact_id.assert_called_once_with(contact_id)
        self.assertEqual(
            [call.args for call in timeline_repository.soft_delete_by_entity.call_args_list],
            [("CALL", call_ids[0]), ("CALL", call_ids[1]), ("CALL", call_ids[2]),
             ("CONTACT", contact_id)],
        )


class UserRetirementCallTests(CallApiTestCase):
    def setUp(self):
        super().setUp()
        self.superadmin = make_user(
            default_test_company(), User.Role.SUPERADMIN, "call-superadmin@example.com",
        )
        self.target = make_user(
            default_test_company(), User.Role.ADMIN, "call-target@example.com",
        )
        self.target_calls = [
            DjangoCallModel.objects.create(
                company=default_test_company(),
                lead=self.lead,
                owner=self.target,
                created_by=self.user,
                outcome="Connected",
                call_start_time=self.now - timedelta(hours=index + 1),
            )
            for index in range(2)
        ]
        self.other_call = DjangoCallModel.objects.create(
            company=default_test_company(),
            lead=self.lead,
            owner=self.user,
            created_by=self.user,
            outcome="Connected",
            call_start_time=self.now - timedelta(hours=9),
        )
        self.client.force_authenticate(self.superadmin)

    def test_deletion_preview_counts_calls_additively(self):
        response = self.client.get(f"/api/users/{self.target.id}/deletion-preview/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["impact"]["calls"], 2)
        self.assertEqual(response.data["permanent_deletions"]["calls"], 2)
        self.assertTrue(response.data["has_related_data"])
        # Pre-existing keys are still present and unchanged in meaning.
        for key in ("leads", "contacts", "accounts", "tasks", "meetings",
                    "reminders", "notifications", "timeline"):
            self.assertIn(key, response.data["impact"])
        for key in ("tasks", "reminders", "notifications"):
            self.assertIn(key, response.data["permanent_deletions"])

    def test_retiring_a_user_permanently_deletes_the_calls_they_own(self):
        response = self.client.delete(
            f"/api/users/{self.target.id}/", {}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)
        self.assertEqual(DjangoCallModel.objects.filter(owner_id=self.target.id).count(), 0)
        self.assertTrue(DjangoCallModel.objects.filter(id=self.other_call.id).exists())

    def test_repository_counts_and_deletes_by_owner(self):
        repository = DjangoCallRepository(company_id=default_test_company().id)

        self.assertEqual(repository.count_by_owner_id(self.target.id), 2)
        self.assertEqual(repository.delete_by_owner_id(self.target.id), 2)
        self.assertEqual(repository.count_by_owner_id(self.target.id), 0)
        self.assertEqual(repository.count_by_owner_id(self.user.id), 1)


class CallTenantIsolationTests(APITestCase):
    """Company A and Company B, each with an ADMIN; B is a stranger to A."""

    def setUp(self):
        self.company_a = make_company("Company A", "calls-company-a")
        self.company_b = make_company("Company B", "calls-company-b")
        self.admin_a = make_user(self.company_a, User.Role.ADMIN, "calls-admin-a@example.com")
        self.admin_b = make_user(self.company_b, User.Role.ADMIN, "calls-admin-b@example.com")
        self.client_a = authenticated_client(self.admin_a)
        self.client_b = authenticated_client(self.admin_b)
        self.now = timezone.now()

        self.lead_a = _make_lead(self.company_a, self.admin_a, "Lead A")
        self.account_a = _make_account(self.company_a, self.admin_a, "Account A")
        self.contact_a = _make_contact(
            self.company_a, self.admin_a, "Contact A", account=self.account_a,
        )
        self.lead_b = _make_lead(self.company_b, self.admin_b, "Lead B")
        self.contact_b = _make_contact(self.company_b, self.admin_b, "Contact B")

        self.lead_call_a = self._log(self.client_a, lead_id=str(self.lead_a.id))
        self.contact_call_a = self._log(
            self.client_a,
            contact_id=str(self.contact_a.id),
            account_id=str(self.account_a.id),
        )
        self.call_b = self._log(self.client_b, lead_id=str(self.lead_b.id))

    def _payload(self, **overrides):
        payload = {
            "outcome": "Connected",
            "call_start_time": (self.now - timedelta(hours=1)).isoformat(),
            "duration_seconds": 60,
            "description": "isolation",
        }
        payload.update(overrides)
        return payload

    def _log(self, client, **overrides):
        response = client.post("/api/calls/", self._payload(**overrides), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data["id"]

    def _snapshot(self):
        return list(
            DjangoCallModel.objects.order_by("id").values_list(
                "id", "description", "duration_seconds", "is_deleted", "company_id",
            )
        )

    def test_each_company_lists_only_its_own_calls(self):
        a_ids = [row["id"] for row in self.client_a.get("/api/calls/").data["results"]]
        b_ids = [row["id"] for row in self.client_b.get("/api/calls/").data["results"]]

        self.assertEqual(set(a_ids), {self.lead_call_a, self.contact_call_a})
        self.assertEqual(b_ids, [self.call_b])

    def test_company_b_cannot_list_company_a_history_by_filter(self):
        for field, value in (("lead_id", self.lead_a.id), ("contact_id", self.contact_a.id)):
            with self.subTest(field):
                response = self.client_b.get("/api/calls/", {"filters": _filters(field, value)})

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["results"], [])
                self.assertEqual(response.data["pagination"]["total"], 0)

    def test_company_b_cannot_read_patch_or_delete_company_a_calls(self):
        before = self._snapshot()

        for call_id in (self.lead_call_a, self.contact_call_a):
            with self.subTest(call_id=call_id):
                foreign = self.client_b.get(f"/api/calls/{call_id}/")
                missing = self.client_b.get(f"/api/calls/{uuid.uuid4()}/")
                self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
                self.assertEqual(foreign.data, missing.data)

                patched = self.client_b.patch(
                    f"/api/calls/{call_id}/", {"description": "hijacked"}, format="json",
                )
                self.assertEqual(patched.status_code, status.HTTP_404_NOT_FOUND)

                deleted = self.client_b.delete(f"/api/calls/{call_id}/")
                self.assertEqual(deleted.status_code, status.HTTP_404_NOT_FOUND)

                timeline = self.client_b.get(f"/api/timeline/calls/{call_id}/")
                self.assertEqual(timeline.status_code, status.HTTP_404_NOT_FOUND)

        self.assertEqual(self._snapshot(), before)
        self.assertEqual(TimelineEvent.objects.filter(event_type="CALL_DELETED").count(), 0)
        self.assertEqual(TimelineEvent.objects.filter(event_type="CALL_UPDATED").count(), 0)

    def test_company_b_cannot_create_calls_against_company_a_records(self):
        before = self._snapshot()

        attempts = {
            "lead of A": {"lead_id": str(self.lead_a.id)},
            "contact of A": {"contact_id": str(self.contact_a.id)},
            "contact of B with account of A": {
                "contact_id": str(self.contact_b.id),
                "account_id": str(self.account_a.id),
            },
            "owner from A": {
                "lead_id": str(self.lead_b.id),
                "owner_id": str(self.admin_a.id),
            },
        }

        for label, overrides in attempts.items():
            with self.subTest(label):
                response = self.client_b.post(
                    "/api/calls/", self._payload(**overrides), format="json",
                )

                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST, response.data,
                )

        self.assertEqual(self._snapshot(), before)

    def test_company_a_history_is_unaffected_by_company_b_activity(self):
        self.client_b.delete(f"/api/calls/{self.lead_call_a}/")
        self.client_b.delete(f"/api/leads/{self.lead_a.id}/delete/")

        response = self.client_a.get(
            "/api/calls/", {"filters": _filters("lead_id", self.lead_a.id)},
        )

        self.assertEqual([row["id"] for row in response.data["results"]], [self.lead_call_a])
        detail = self.client_a.get(f"/api/calls/{self.lead_call_a}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["total_calls_for_record"], 1)


class CallModuleSanityTests(SimpleTestCase):
    def test_urls_resolve(self):
        from django.urls import resolve, reverse

        call_id = uuid.uuid4()

        self.assertEqual(reverse("calls"), "/api/calls/")
        self.assertEqual(reverse("call-detail", args=[call_id]), f"/api/calls/{call_id}/")
        self.assertEqual(reverse("call-timeline", args=[call_id]), f"/api/timeline/calls/{call_id}/")
        self.assertEqual(
            resolve(f"/api/timeline/calls/{call_id}/").kwargs["entity_type"], "CALL",
        )
