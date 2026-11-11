from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from src.modules.calls.application.services.call_history import build_record_history
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.email_activity.domain.enums.record_type import RecordType
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
    token_client,
)
from src.modules.timeline.domain.enums.timeline_entity_type import TimelineEntityType
from src.modules.timeline.domain.enums.timeline_event_type import TimelineEventType
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import (
    DjangoTimelineRepository,
)
from src.modules.timeline.infrastructure.persistence.models import (
    TimelineEvent,
    TimelineEventTarget,
)
from src.modules.users.infrastructure.persistence.models import User

URL = "/api/email-activity/compose/"
EVENT = "EMAIL_COMPOSED"


def make_contact(company, owner, name, **extra):
    now = timezone.now()
    return DjangoContactModel.objects.create(
        company=company,
        contact_owner=owner,
        name=name,
        created_by=owner,
        created_at=now,
        modified_by=owner,
        updated_at=now,
        **extra,
    )


def make_lead(company, owner, name, **extra):
    return DjangoLeadModel.objects.create(
        company=company, owner=owner, name=name, **extra
    )


def contact_target(record):
    return {"record_type": "CONTACT", "record_id": str(record.id)}


def lead_target(record):
    return {"record_type": "LEAD", "record_id": str(record.id)}


class EmailComposeApiTestCase(APITestCase):
    """Company A (the caller's) and company B, each with an admin."""

    def setUp(self):
        self.company = make_company("Mail Co")
        self.other_company = make_company("Other Mail Co")
        self.admin = make_user(self.company, User.Role.ADMIN, name="Admin One")
        self.other_admin = make_user(self.other_company, User.Role.ADMIN)
        self.client = authenticated_client(self.admin)

        self.ann = make_contact(
            self.company, self.admin, "Ann Alpha", email="ann@example.com"
        )
        self.carl = make_contact(self.company, self.admin, "Carl Alpha")
        self.lee = make_lead(
            self.company, self.admin, "Lee Lead", email="lee@example.com"
        )
        self.bob = make_contact(
            self.other_company, self.other_admin, "Bob Beta", email="bob@example.com"
        )
        self.bea = make_lead(
            self.other_company, self.other_admin, "Bea Beta", email="bea@example.com"
        )

    def post(self, targets, client=None, **extra):
        payload = {
            "client_ref": str(uuid4()),
            "channel": "GMAIL_COMPOSE",
            "targets": targets,
            **extra,
        }
        return (client or self.client).post(URL, payload, format="json")

    def timeline(self, kind, record, client=None):
        response = (client or self.client).get(f"/api/timeline/{kind}/{record.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def composed(self, kind, record, client=None):
        return [
            event
            for event in self.timeline(kind, record, client)
            if event["event_type"] == EVENT
        ]

    def count_events(self):
        return TimelineEvent.objects.filter(event_type=EVENT).count()

    def assertDetail400(self, response, fragment=None):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(set(response.data), {"detail"})
        self.assertIsInstance(response.data["detail"], str)
        if fragment is not None:
            self.assertIn(fragment, response.data["detail"])


class LogComposeTests(EmailComposeApiTestCase):
    def test_contact_gets_an_event_visible_in_its_timeline(self):
        ref = str(uuid4())

        response = self.post(
            [contact_target(self.ann)],
            client_ref=ref,
            subject="Hello Ann",
            batch_index=1,
            batch_total=3,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            response.data, {"logged": 1, "already_logged": 0, "not_found": []}
        )
        events = self.composed("contacts", self.ann)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["message"], "Email opened in Gmail by Admin One")
        self.assertEqual(event["actor"]["id"], str(self.admin.id))
        self.assertEqual(event["actor"]["name"], "Admin One")
        self.assertEqual(
            event["metadata"],
            {
                "client_ref": ref,
                "channel": "GMAIL_COMPOSE",
                "subject": "Hello Ann",
                "recipient_email": "ann@example.com",
                "batch_index": 1,
                "batch_total": 3,
            },
        )
        self.assertEqual(
            [(t["entity_type"], t["entity_id"]) for t in event["targets"]],
            [("CONTACT", str(self.ann.id))],
        )

    def test_lead_gets_an_event_visible_in_its_timeline(self):
        response = self.post([lead_target(self.lee)])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        events = self.composed("leads", self.lee)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "EMAIL_COMPOSED")
        self.assertEqual(events[0]["metadata"]["recipient_email"], "lee@example.com")
        self.assertEqual(
            [(t["entity_type"], t["entity_id"]) for t in events[0]["targets"]],
            [("LEAD", str(self.lee.id))],
        )

    def test_one_event_per_target_and_no_record_sees_the_others(self):
        response = self.post(
            [contact_target(self.ann), contact_target(self.carl), lead_target(self.lee)]
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["logged"], 3)
        self.assertEqual(self.count_events(), 3)

        for kind, record, own_email in (
            ("contacts", self.ann, "ann@example.com"),
            ("contacts", self.carl, None),
            ("leads", self.lee, "lee@example.com"),
        ):
            events = self.composed(kind, record)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["metadata"]["recipient_email"], own_email)
            self.assertEqual(len(events[0]["targets"]), 1)
            text = repr(events[0])
            for other in ("ann@example.com", "lee@example.com"):
                if other != own_email:
                    self.assertNotIn(other, text)

    def test_duplicate_targets_in_one_request_are_collapsed(self):
        response = self.post([contact_target(self.ann)] * 3)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["logged"], 1)
        self.assertEqual(self.count_events(), 1)

    def test_recipient_email_is_the_records_email_at_that_moment(self):
        self.post([contact_target(self.ann)])
        DjangoContactModel.objects.filter(id=self.ann.id).update(
            email="ann.new@example.com"
        )

        self.post([contact_target(self.ann)])

        emails = {
            event["metadata"]["recipient_email"]
            for event in self.composed("contacts", self.ann)
        }
        self.assertEqual(emails, {"ann@example.com", "ann.new@example.com"})

    def test_subject_is_trimmed_and_truncated(self):
        self.post([contact_target(self.ann)], subject="   " + "x" * 300 + "   ")

        subject = self.composed("contacts", self.ann)[0]["metadata"]["subject"]
        self.assertEqual(subject, "x" * 200)

    def test_missing_optional_fields_are_stored_as_null(self):
        self.post([contact_target(self.ann)])

        metadata = self.composed("contacts", self.ann)[0]["metadata"]
        self.assertIsNone(metadata["subject"])
        self.assertIsNone(metadata["batch_index"])
        self.assertIsNone(metadata["batch_total"])

    def test_other_timeline_events_are_not_affected(self):
        self.post([contact_target(self.ann)])

        types = [event["event_type"] for event in self.timeline("contacts", self.ann)]
        self.assertEqual(types, [EVENT])


class IdempotencyTests(EmailComposeApiTestCase):
    def test_retry_with_the_same_client_ref_writes_nothing_new(self):
        ref = str(uuid4())
        targets = [contact_target(self.ann), lead_target(self.lee)]

        first = self.post(targets, client_ref=ref)
        second = self.post(targets, client_ref=ref)

        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertEqual(
            second.data, {"logged": 0, "already_logged": 2, "not_found": []}
        )
        self.assertEqual(self.count_events(), 2)
        self.assertEqual(len(self.composed("contacts", self.ann)), 1)
        self.assertEqual(len(self.composed("leads", self.lee)), 1)

    def test_a_retry_that_adds_a_target_only_logs_the_new_one(self):
        ref = str(uuid4())
        self.post([contact_target(self.ann)], client_ref=ref)

        response = self.post(
            [contact_target(self.ann), contact_target(self.carl)], client_ref=ref
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            response.data, {"logged": 1, "already_logged": 1, "not_found": []}
        )
        self.assertEqual(self.count_events(), 2)

    def test_a_new_client_ref_is_a_new_compose_action(self):
        self.post([contact_target(self.ann)])
        response = self.post([contact_target(self.ann)])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(self.composed("contacts", self.ann)), 2)

    def test_client_ref_spelling_does_not_defeat_the_check(self):
        ref = uuid4()
        self.post([contact_target(self.ann)], client_ref=str(ref).upper())

        response = self.post([contact_target(self.ann)], client_ref=ref.hex)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(self.count_events(), 1)

    def test_the_same_client_ref_in_another_company_is_independent(self):
        ref = str(uuid4())
        self.post([contact_target(self.ann)], client_ref=ref)

        response = self.post(
            [contact_target(self.bob)],
            client_ref=ref,
            client=authenticated_client(self.other_admin),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(self.count_events(), 2)

    def test_a_soft_deleted_event_does_not_count_as_logged(self):
        ref = str(uuid4())
        self.post([contact_target(self.ann)], client_ref=ref)
        TimelineEvent.objects.filter(event_type=EVENT).update(is_deleted=True)

        response = self.post([contact_target(self.ann)], client_ref=ref)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["logged"], 1)


class NotFoundTests(EmailComposeApiTestCase):
    def test_records_of_another_company_are_not_found_and_nothing_is_written(self):
        response = self.post([contact_target(self.bob), lead_target(self.bea)])

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["logged"], 0)
        self.assertEqual(response.data["already_logged"], 0)
        self.assertCountEqual(
            response.data["not_found"],
            [
                {"record_type": "CONTACT", "record_id": str(self.bob.id)},
                {"record_type": "LEAD", "record_id": str(self.bea.id)},
            ],
        )
        self.assertEqual(self.count_events(), 0)
        other = authenticated_client(self.other_admin)
        self.assertEqual(self.composed("contacts", self.bob, other), [])
        self.assertEqual(self.composed("leads", self.bea, other), [])

    def test_valid_targets_are_still_logged_next_to_foreign_ones(self):
        response = self.post([contact_target(self.bob), contact_target(self.ann)])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["logged"], 1)
        self.assertEqual(
            response.data["not_found"],
            [{"record_type": "CONTACT", "record_id": str(self.bob.id)}],
        )
        self.assertEqual(len(self.composed("contacts", self.ann)), 1)

    def test_soft_deleted_and_unknown_records_are_not_found(self):
        DjangoContactModel.objects.filter(id=self.carl.id).update(is_deleted=True)
        DjangoLeadModel.objects.filter(id=self.lee.id).update(is_deleted=True)
        ghost = uuid4()

        response = self.post(
            [
                contact_target(self.carl),
                lead_target(self.lee),
                {"record_type": "LEAD", "record_id": str(ghost)},
            ]
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["logged"], 0)
        self.assertEqual(len(response.data["not_found"]), 3)
        self.assertEqual(self.count_events(), 0)

    def test_the_record_type_must_match_the_id(self):
        response = self.post([lead_target(self.ann)])  # a contact id, sent as LEAD

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["logged"], 0)
        self.assertEqual(len(response.data["not_found"]), 1)

    def test_a_converted_lead_can_still_be_logged_like_its_detail_view(self):
        DjangoLeadModel.objects.filter(id=self.lee.id).update(is_converted=True)

        response = self.post([lead_target(self.lee)])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)


class LeadRoleRulesTests(EmailComposeApiTestCase):
    """The lead LIST is admin-only, but the lead DETAIL view (opening a lead)
    has no role check. Logging mirrors opening a record, so every company
    role may log against a lead of its own company."""

    def test_the_read_rules_this_decision_mirrors(self):
        executive = make_user(self.company, User.Role.SALES_EXECUTIVE)
        client = authenticated_client(executive)

        self.assertEqual(client.get("/api/leads/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            client.get(f"/api/leads/{self.lee.id}/").status_code, status.HTTP_200_OK
        )
        self.assertEqual(
            client.get(f"/api/contacts/{self.ann.id}/").status_code, status.HTTP_200_OK
        )

    def test_every_company_role_can_log_against_leads_and_contacts(self):
        for role in (
            User.Role.SUPERADMIN,
            User.Role.ADMIN,
            User.Role.SALES_MANAGER,
            User.Role.SALES_EXECUTIVE,
        ):
            with self.subTest(role=role):
                user = make_user(self.company, role)

                response = self.post(
                    [lead_target(self.lee), contact_target(self.ann)],
                    client=authenticated_client(user),
                )

                self.assertEqual(
                    response.status_code, status.HTTP_201_CREATED, response.data
                )
                self.assertEqual(response.data["logged"], 2)

    def test_a_platform_superadmin_has_no_company_and_is_refused(self):
        platform = make_user(None, role=User.Role.PLATFORM_SUPERADMIN)

        response = self.post(
            [lead_target(self.lee)], client=authenticated_client(platform)
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.count_events(), 0)

    def test_an_inactive_user_is_refused(self):
        inactive = make_user(self.company, User.Role.ADMIN, is_active=False)

        response = self.post(
            [lead_target(self.lee)], client=authenticated_client(inactive)
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.count_events(), 0)


class AuthenticationTests(EmailComposeApiTestCase):
    def test_unauthenticated_request_is_401(self):
        response = self.post([contact_target(self.ann)], client=APIClient())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.count_events(), 0)

    def test_the_actor_is_the_token_user_never_the_body(self):
        other_user = make_user(self.company, User.Role.ADMIN, name="Somebody Else")
        sales = make_user(self.company, User.Role.SALES_EXECUTIVE, name="Sam Sales")

        response = self.post(
            [contact_target(self.ann)],
            client=token_client(sales),
            actor_id=str(other_user.id),
            actor="Somebody Else",
            user_id=str(other_user.id),
            company_id=str(self.other_company.id),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        event = self.composed("contacts", self.ann)[0]
        self.assertEqual(event["actor"]["id"], str(sales.id))
        self.assertEqual(event["message"], "Email opened in Gmail by Sam Sales")
        stored = TimelineEvent.objects.get(event_type=EVENT)
        self.assertEqual(stored.actor_id, sales.id)
        self.assertEqual(stored.company_id, self.company.id)

    def test_a_company_id_in_the_body_cannot_reach_another_company(self):
        response = self.post(
            [contact_target(self.bob)], company_id=str(self.other_company.id)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["logged"], 0)
        self.assertEqual(self.count_events(), 0)


class ValidationTests(EmailComposeApiTestCase):
    def test_fifty_targets_are_accepted(self):
        contacts = [
            make_contact(self.company, self.admin, f"Bulk {i:02d}") for i in range(50)
        ]

        response = self.post([contact_target(c) for c in contacts])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["logged"], 50)

    def test_fifty_one_targets_are_refused_and_nothing_is_written(self):
        response = self.post([contact_target(self.ann)] * 51)

        self.assertDetail400(response, "50")
        self.assertEqual(self.count_events(), 0)

    def test_no_targets_is_refused(self):
        self.assertDetail400(self.post([]), "at least one target")

    def test_targets_must_be_a_list_of_valid_entries(self):
        for bad in (
            "nope",
            ["nope"],
            [{"record_type": "ACCOUNT", "record_id": str(uuid4())}],
            [{"record_type": "contact", "record_id": str(uuid4())}],
            [{"record_type": "CONTACT"}],
            [{"record_type": "CONTACT", "record_id": "not-a-uuid"}],
            [{"record_type": "CONTACT", "record_id": 12}],
            [{"record_id": str(uuid4())}],
        ):
            with self.subTest(targets=bad):
                self.assertDetail400(self.post(bad))

    def test_targets_are_required(self):
        response = self.client.post(
            URL, {"client_ref": str(uuid4()), "channel": "GMAIL_COMPOSE"}, format="json"
        )

        self.assertDetail400(response, "targets")

    def test_client_ref_must_be_a_uuid(self):
        for bad in ("abc", "", 5, None, [str(uuid4())]):
            with self.subTest(client_ref=bad):
                self.assertDetail400(
                    self.post([contact_target(self.ann)], client_ref=bad)
                )

    def test_client_ref_is_required(self):
        response = self.client.post(
            URL,
            {"channel": "GMAIL_COMPOSE", "targets": [contact_target(self.ann)]},
            format="json",
        )

        self.assertDetail400(response, "client_ref")

    def test_only_gmail_compose_is_accepted_as_channel(self):
        for bad in ("SMTP", "gmail_compose", "", None):
            with self.subTest(channel=bad):
                self.assertDetail400(
                    self.post([contact_target(self.ann)], channel=bad)
                )
        self.assertEqual(self.count_events(), 0)

    def test_channel_is_required(self):
        response = self.client.post(
            URL,
            {"client_ref": str(uuid4()), "targets": [contact_target(self.ann)]},
            format="json",
        )

        self.assertDetail400(response, "channel")

    def test_batch_numbers_are_validated(self):
        for extra, fragment in (
            ({"batch_index": 4, "batch_total": 3}, "batch_index"),
            ({"batch_index": 0}, "batch_index"),
            ({"batch_total": 0}, "batch_total"),
            ({"batch_index": -1, "batch_total": 3}, "batch_index"),
            ({"batch_index": "x"}, "batch_index"),
            ({"batch_total": 1.5}, "batch_total"),
            ({"batch_index": True}, "batch_index"),
        ):
            with self.subTest(extra=extra):
                self.assertDetail400(
                    self.post([contact_target(self.ann)], **extra), fragment
                )
        self.assertEqual(self.count_events(), 0)

    def test_batch_index_equal_to_total_is_accepted(self):
        response = self.post(
            [contact_target(self.ann)], batch_index=3, batch_total=3
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_a_subject_that_is_not_a_string_is_refused(self):
        for bad in ({"a": 1}, ["x"], True):
            with self.subTest(subject=bad):
                self.assertDetail400(self.post([contact_target(self.ann)], subject=bad))

    def test_a_null_or_blank_subject_is_accepted(self):
        for value in (None, "", "   "):
            with self.subTest(subject=value):
                response = self.post([contact_target(self.ann)], subject=value)
                self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        subjects = {e["metadata"]["subject"] for e in self.composed("contacts", self.ann)}
        self.assertEqual(subjects, {None})

    def test_a_subject_with_a_null_character_is_refused_not_a_500(self):
        self.assertDetail400(self.post([contact_target(self.ann)], subject="a\x00b"))

    def test_the_body_must_be_an_object(self):
        response = self.client.post(URL, [1, 2], format="json")

        self.assertDetail400(response)


class TimelineWiringTests(EmailComposeApiTestCase):
    """The new event type must not disturb the other timeline consumers."""

    def test_enum_value_and_entity_types_match_the_timeline_module(self):
        self.assertEqual(TimelineEventType.EMAIL_COMPOSED.value, EVENT)
        for record_type in RecordType:
            self.assertEqual(
                record_type.value, TimelineEntityType[record_type.name].value
            )

    def test_event_type_fits_the_column_and_is_not_a_call_event(self):
        self.assertLessEqual(
            len(EVENT), TimelineEvent._meta.get_field("event_type").max_length
        )
        self.assertFalse(EVENT.startswith("CALL_"))

    def test_call_history_ignores_the_event(self):
        events = [
            {
                "id": uuid4(),
                "event_type": EVENT,
                "metadata": {"client_ref": str(uuid4())},
            }
        ]

        self.assertEqual(build_record_history(events, {}), [])

    def test_the_event_does_not_become_the_latest_call_event(self):
        self.post([contact_target(self.ann)])

        latest = DjangoTimelineRepository(
            company_id=self.company.id
        ).get_latest_for_entities("CONTACT", [self.ann.id], event_type_prefix="CALL_")

        self.assertEqual(latest, {})

    def test_deleting_the_record_hides_its_events(self):
        self.post([contact_target(self.ann), contact_target(self.carl)])

        DjangoTimelineRepository(company_id=self.company.id).soft_delete_by_entity(
            "CONTACT", self.ann.id
        )

        events = TimelineEvent.objects.filter(event_type=EVENT)
        self.assertEqual(events.filter(is_deleted=False).count(), 1)
        self.assertEqual(
            TimelineEventTarget.objects.filter(
                entity_id=self.carl.id, is_deleted=False
            ).count(),
            1,
        )


class TimelineRepositoryClientRefTests(TestCase):
    """``DjangoTimelineRepository.get_targets_with_client_ref``."""

    def setUp(self):
        self.company = make_company("Repo Co")
        self.other_company = make_company("Repo Other Co")
        self.actor = make_user(self.company, User.Role.ADMIN)
        self.other_actor = make_user(self.other_company, User.Role.ADMIN)
        self.repo = DjangoTimelineRepository(company_id=self.company.id)
        self.other_repo = DjangoTimelineRepository(company_id=self.other_company.id)
        self.contact_id, self.lead_id, self.untouched_id = uuid4(), uuid4(), uuid4()

    def record(self, repo, actor, target, ref, event_type=EVENT):
        repo.record(
            event_type=event_type,
            actor_id=actor.id,
            message="Email opened in Gmail by someone",
            metadata={"client_ref": ref},
            targets=[target],
        )

    def ask(self, repo, ref, targets, event_type=EVENT):
        return repo.get_targets_with_client_ref(
            event_type=event_type, client_ref=ref, targets=targets
        )

    def test_returns_only_the_targets_with_that_client_ref(self):
        ref = str(uuid4())
        self.record(self.repo, self.actor, ("CONTACT", self.contact_id), ref)
        self.record(self.repo, self.actor, ("LEAD", self.lead_id), ref)
        self.record(self.repo, self.actor, ("CONTACT", self.untouched_id), str(uuid4()))

        found = self.ask(
            self.repo,
            ref,
            [
                ("CONTACT", self.contact_id),
                ("LEAD", self.lead_id),
                ("CONTACT", self.untouched_id),
            ],
        )

        self.assertEqual(
            found, {("CONTACT", self.contact_id), ("LEAD", self.lead_id)}
        )

    def test_it_is_a_single_query_for_all_targets(self):
        ref = str(uuid4())
        self.record(self.repo, self.actor, ("CONTACT", self.contact_id), ref)
        targets = [("CONTACT", self.contact_id), ("LEAD", self.lead_id)] + [
            ("CONTACT", uuid4()) for _ in range(20)
        ]

        with self.assertNumQueries(1):
            self.ask(self.repo, ref, targets)

    def test_entity_type_must_match(self):
        ref = str(uuid4())
        self.record(self.repo, self.actor, ("CONTACT", self.contact_id), ref)

        self.assertEqual(self.ask(self.repo, ref, [("LEAD", self.contact_id)]), set())

    def test_event_type_must_match(self):
        ref = str(uuid4())
        self.record(
            self.repo, self.actor, ("CONTACT", self.contact_id), ref,
            event_type="CONTACT_UPDATED",
        )

        self.assertEqual(
            self.ask(self.repo, ref, [("CONTACT", self.contact_id)]), set()
        )

    def test_other_companies_events_are_invisible(self):
        ref = str(uuid4())
        self.record(self.other_repo, self.other_actor, ("CONTACT", self.contact_id), ref)

        self.assertEqual(
            self.ask(self.repo, ref, [("CONTACT", self.contact_id)]), set()
        )
        self.assertEqual(
            self.ask(self.other_repo, ref, [("CONTACT", self.contact_id)]),
            {("CONTACT", self.contact_id)},
        )

    def test_soft_deleted_events_and_targets_are_ignored(self):
        ref = str(uuid4())
        self.record(self.repo, self.actor, ("CONTACT", self.contact_id), ref)
        self.record(self.repo, self.actor, ("LEAD", self.lead_id), ref)
        TimelineEvent.objects.filter(targets__entity_id=self.contact_id).update(
            is_deleted=True
        )
        TimelineEventTarget.objects.filter(entity_id=self.lead_id).update(
            is_deleted=True
        )

        found = self.ask(
            self.repo, ref, [("CONTACT", self.contact_id), ("LEAD", self.lead_id)]
        )

        self.assertEqual(found, set())

    def test_no_targets_means_no_query(self):
        with self.assertNumQueries(0):
            self.assertEqual(self.ask(self.repo, str(uuid4()), []), set())
