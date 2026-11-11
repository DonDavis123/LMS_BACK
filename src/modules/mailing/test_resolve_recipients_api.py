import json
from datetime import timedelta
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.accounts.infrastructure.persistence.django_account_repository import (
    DjangoAccountRepository,
)
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.contacts.infrastructure.persistence.contacts_repository import (
    DjangoContactRepository,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_repository import (
    DjangoLeadRepository,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

URL = "/api/mail/recipients/resolve/"


def make_account(company, owner, name, created_at=None, **extra):
    now = created_at or timezone.now()
    return DjangoAccountModel.objects.create(
        company=company,
        account_owner=owner,
        account_name=name,
        created_by=owner,
        created_at=now,
        modified_by=owner,
        updated_at=now,
        **extra,
    )


def contact_fields(company, owner, name, account=None, created_at=None, **extra):
    created_at = created_at or timezone.now()
    return dict(
        company=company,
        account=account,
        contact_owner=owner,
        name=name,
        created_by=owner,
        created_at=created_at,
        modified_by=owner,
        updated_at=created_at,
        **extra,
    )


def make_contact(company, owner, name, account=None, **extra):
    return DjangoContactModel.objects.create(
        **contact_fields(company, owner, name, account=account, **extra)
    )


def bulk_contacts(company, owner, count, prefix, extra=None):
    """``count`` contacts "<prefix> 000", "<prefix> 001", ... where a higher
    number is newer, so the list (newest first) shows the highest first.
    ``extra`` is a dict of fields, or a function of the index returning one."""
    base = timezone.now() - timedelta(days=1)
    return DjangoContactModel.objects.bulk_create(
        [
            DjangoContactModel(
                **contact_fields(
                    company,
                    owner,
                    f"{prefix} {index:03d}",
                    created_at=base + timedelta(seconds=index),
                    email=f"{prefix.lower().replace(' ', '')}{index:03d}@mass.test",
                    **(extra(index) if callable(extra) else (extra or {})),
                )
            )
            for index in range(count)
        ],
        batch_size=500,
    )


def make_lead(company, owner, name, **extra):
    return DjangoLeadModel.objects.create(
        company=company, owner=owner, name=name, **extra
    )


def ids(*records):
    return [str(record.id) for record in records]


def without_id(entries):
    return [{k: v for k, v in entry.items() if k != "record_id"} for entry in entries]


class MailRecipientsApiTestCase(APITestCase):
    """Company A (the caller's) and company B, with an admin each."""

    def setUp(self):
        self.company = make_company("Mail Co")
        self.other_company = make_company("Other Mail Co")
        self.admin = make_user(self.company, User.Role.ADMIN, name="Admin One")
        self.other_admin = make_user(self.other_company, User.Role.ADMIN)
        self.client = authenticated_client(self.admin)

    def post(self, entity, selection, client=None, **extra):
        payload = {"entity": entity, "selection": selection, **extra}
        return (client or self.client).post(URL, payload, format="json")

    def assertDetail400(self, response, fragment=None):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(set(response.data), {"detail"})
        self.assertIsInstance(response.data["detail"], str)
        if fragment is not None:
            self.assertIn(fragment, response.data["detail"])


class ContactsIdsModeTests(MailRecipientsApiTestCase):
    def setUp(self):
        super().setUp()
        owner = self.admin
        self.account = make_account(self.company, owner, "Acme Corp")

        self.ok = make_contact(
            self.company, owner, "Ann Alpha", account=self.account,
            email="Ann@Acme.test", secondary_email="ann.alt@acme.test",
        )
        self.opted_out = make_contact(
            self.company, owner, "Out Out", email="out@acme.test", email_opt_out=True,
        )
        self.no_email = make_contact(self.company, owner, "No Mail")
        self.bad_email = make_contact(self.company, owner, "Bad Mail", email="not-an-email")
        self.duplicate = make_contact(self.company, owner, "Dup Dup", email="ann@acme.test")
        self.deleted = make_contact(
            self.company, owner, "Gone", email="gone@acme.test", is_deleted=True,
        )
        self.foreign = make_contact(
            self.other_company, self.other_admin, "Foreign", email="foreign@other.test",
        )
        self.unknown = uuid4()

    def everyone(self):
        return ids(
            self.ok, self.opted_out, self.no_email, self.bad_email,
            self.duplicate, self.deleted, self.foreign,
        ) + [str(self.unknown)]

    def test_response_has_exactly_the_contracted_shape(self):
        response = self.post("contacts", {"mode": "ids", "ids": self.everyone()})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        data = response.json()
        self.assertEqual(list(data), ["entity", "summary", "recipients", "skipped", "batches"])
        self.assertEqual(data["entity"], "contacts")
        self.assertEqual(
            data["summary"], {"selected": 8, "eligible": 1, "skipped": 7, "batches": 1}
        )
        self.assertEqual(
            data["recipients"],
            [
                {
                    "record_id": str(self.ok.id),
                    "record_type": "CONTACT",
                    "name": "Ann Alpha",
                    "email": "Ann@Acme.test",
                    "email_kind": "PRIMARY",
                    "account_name": "Acme Corp",
                    "source_account_id": None,
                }
            ],
        )
        self.assertEqual(
            data["skipped"],
            [
                {"record_id": str(self.opted_out.id), "record_type": "CONTACT",
                 "name": "Out Out", "reason": "OPTED_OUT"},
                {"record_id": str(self.no_email.id), "record_type": "CONTACT",
                 "name": "No Mail", "reason": "NO_EMAIL"},
                {"record_id": str(self.bad_email.id), "record_type": "CONTACT",
                 "name": "Bad Mail", "reason": "INVALID_EMAIL"},
                {"record_id": str(self.duplicate.id), "record_type": "CONTACT",
                 "name": "Dup Dup", "reason": "DUPLICATE_EMAIL"},
                {"record_id": str(self.deleted.id), "record_type": "CONTACT",
                 "name": "", "reason": "NOT_FOUND"},
                {"record_id": str(self.foreign.id), "record_type": "CONTACT",
                 "name": "", "reason": "NOT_FOUND"},
                {"record_id": str(self.unknown), "record_type": "CONTACT",
                 "name": "", "reason": "NOT_FOUND"},
            ],
        )
        self.assertEqual(data["batches"], [["ann@acme.test"]])

    def test_secondary_email_is_an_extra_recipient_only_when_asked_for(self):
        selection = {"mode": "ids", "ids": ids(self.ok)}

        without = self.post("contacts", selection).json()
        self.assertEqual([r["email"] for r in without["recipients"]], ["Ann@Acme.test"])

        with_secondary = self.post(
            "contacts", selection, include_secondary_email=True
        ).json()
        self.assertEqual(
            [(r["email"], r["email_kind"]) for r in with_secondary["recipients"]],
            [("Ann@Acme.test", "PRIMARY"), ("ann.alt@acme.test", "SECONDARY")],
        )
        self.assertEqual(
            with_secondary["summary"],
            {"selected": 1, "eligible": 2, "skipped": 0, "batches": 1},
        )
        self.assertEqual(
            with_secondary["batches"], [["ann@acme.test", "ann.alt@acme.test"]]
        )

    def test_opt_out_is_skipped_and_never_batched(self):
        data = self.post("contacts", {"mode": "ids", "ids": ids(self.opted_out)}).json()
        self.assertEqual(data["recipients"], [])
        self.assertEqual([s["reason"] for s in data["skipped"]], ["OPTED_OUT"])
        self.assertEqual(data["batches"], [])
        self.assertEqual(
            data["summary"], {"selected": 1, "eligible": 0, "skipped": 1, "batches": 0}
        )

    def test_cross_company_soft_deleted_and_unknown_ids_look_the_same(self):
        data = self.post(
            "contacts",
            {"mode": "ids", "ids": ids(self.foreign, self.deleted) + [str(self.unknown)]},
        ).json()

        self.assertEqual(data["recipients"], [])
        self.assertEqual({s["reason"] for s in data["skipped"]}, {"NOT_FOUND"})
        entries = without_id(data["skipped"])
        self.assertEqual(entries[0], entries[1])
        self.assertEqual(entries[1], entries[2])
        self.assertNotIn("foreign@other.test", json.dumps(data))
        self.assertNotIn("Foreign", json.dumps(data))

    def test_company_in_the_body_is_ignored(self):
        response = self.post(
            "contacts",
            {"mode": "ids", "ids": ids(self.foreign)},
            company_id=str(self.other_company.id),
            company=str(self.other_company.id),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["skipped"][0]["reason"], "NOT_FOUND")

    def test_other_company_user_only_sees_their_own_contacts(self):
        other_client = authenticated_client(self.other_admin)
        data = self.post(
            "contacts", {"mode": "ids", "ids": ids(self.foreign, self.ok)}, client=other_client
        ).json()
        self.assertEqual([r["email"] for r in data["recipients"]], ["foreign@other.test"])
        self.assertEqual([s["reason"] for s in data["skipped"]], ["NOT_FOUND"])

    def test_repeated_ids_count_once(self):
        data = self.post(
            "contacts", {"mode": "ids", "ids": ids(self.ok, self.ok)}
        ).json()
        self.assertEqual(data["summary"]["selected"], 1)
        self.assertEqual(len(data["recipients"]), 1)

    def test_batching_by_batch_size(self):
        contacts = bulk_contacts(self.company, self.admin, 45, "Batch", {})
        selection = {"mode": "ids", "ids": ids(*contacts)}

        default = self.post("contacts", selection).json()
        self.assertEqual([len(b) for b in default["batches"]], [40, 5])
        self.assertEqual(default["summary"]["batches"], 2)

        fifty = self.post("contacts", selection, batch_size=50).json()
        self.assertEqual([len(b) for b in fifty["batches"]], [45])

        ten = self.post("contacts", selection, batch_size=10).json()
        self.assertEqual([len(b) for b in ten["batches"]], [10, 10, 10, 10, 5])
        flat = [address for batch in ten["batches"] for address in batch]
        self.assertEqual(flat, [r["email"].lower() for r in ten["recipients"]])

    def test_exactly_500_ids_are_accepted(self):
        data = self.post(
            "contacts", {"mode": "ids", "ids": [str(uuid4()) for _ in range(500)]}
        ).json()
        self.assertEqual(data["summary"]["selected"], 500)
        self.assertEqual(data["summary"]["skipped"], 500)


class ContactsFilterModeTests(MailRecipientsApiTestCase):
    def setUp(self):
        super().setUp()
        # 120 contacts = three pages of 50 in the list. Even numbers are Sales.
        self.bulk = bulk_contacts(
            self.company,
            self.admin,
            120,
            "Bulk",
            lambda index: {"department": "Sales" if index % 2 == 0 else "Support"},
        )
        self.other_named = make_contact(
            self.company, self.admin, "Someone Else", email="else@acme.test"
        )
        self.deleted_bulk = make_contact(
            self.company, self.admin, "Bulk Deleted", email="deleted@mass.test",
            is_deleted=True,
        )
        bulk_contacts(self.other_company, self.other_admin, 5, "Bulk")

    def filter_selection(self, **kwargs):
        return {"mode": "filter", **kwargs}

    def test_search_reads_every_page_of_the_callers_company_only(self):
        data = self.post(
            "contacts", self.filter_selection(search="bulk"), batch_size=50
        ).json()

        self.assertEqual(data["summary"]["selected"], 120)
        self.assertEqual(data["summary"]["eligible"], 120)
        self.assertEqual(data["summary"]["skipped"], 0)
        self.assertEqual([len(b) for b in data["batches"]], [50, 50, 20])
        # Same order as the list: newest first.
        self.assertEqual(data["recipients"][0]["name"], "Bulk 119")
        self.assertEqual(data["recipients"][-1]["name"], "Bulk 000")
        self.assertEqual(len({r["record_id"] for r in data["recipients"]}), 120)
        self.assertNotIn("deleted@mass.test", [r["email"] for r in data["recipients"]])

    def test_no_search_and_no_filters_selects_the_whole_list(self):
        data = self.post("contacts", self.filter_selection()).json()
        self.assertEqual(data["summary"]["selected"], 121)  # 120 + Someone Else

    def test_filters_narrow_the_selection_like_the_list(self):
        filters = [{"field": "department", "operator": "equals", "value": "Sales"}]
        data = self.post(
            "contacts", self.filter_selection(search="bulk", filters=filters)
        ).json()
        self.assertEqual(data["summary"]["selected"], 60)
        self.assertTrue(all(int(r["name"][-3:]) % 2 == 0 for r in data["recipients"]))

    def test_exclude_ids_remove_records_from_the_selection(self):
        filters = [{"field": "department", "operator": "equals", "value": "Sales"}]
        excluded = [self.bulk[0], self.bulk[2], self.bulk[118]]
        data = self.post(
            "contacts",
            self.filter_selection(
                search="bulk", filters=filters,
                exclude_ids=ids(*excluded) + [str(uuid4())],
            ),
        ).json()

        self.assertEqual(data["summary"]["selected"], 57)
        self.assertEqual(data["summary"]["eligible"], 57)
        self.assertEqual(data["summary"]["skipped"], 0)  # excluded is not skipped
        returned = {r["record_id"] for r in data["recipients"]}
        for contact in excluded:
            self.assertNotIn(str(contact.id), returned)

    def test_exclude_ids_from_another_company_change_nothing(self):
        foreign = DjangoContactModel.objects.filter(company=self.other_company).first()
        data = self.post(
            "contacts", self.filter_selection(search="bulk", exclude_ids=[str(foreign.id)])
        ).json()
        self.assertEqual(data["summary"]["selected"], 120)

    def test_contact_rules_apply_in_filter_mode(self):
        opted = make_contact(
            self.company, self.admin, "Bulk Optout", email="optout@mass.test",
            email_opt_out=True,
        )
        no_email = make_contact(self.company, self.admin, "Bulk Noemail")
        # Newer than every bulk contact, so the list shows it first and its
        # address is the one that is kept; "Bulk 000" becomes the duplicate.
        twin = make_contact(
            self.company, self.admin, "Bulk Twin", email="BULK000@mass.test"
        )
        data = self.post("contacts", self.filter_selection(search="bulk")).json()

        reasons = {s["record_id"]: s["reason"] for s in data["skipped"]}
        self.assertEqual(reasons[str(opted.id)], "OPTED_OUT")
        self.assertEqual(reasons[str(no_email.id)], "NO_EMAIL")
        self.assertEqual(reasons[str(self.bulk[0].id)], "DUPLICATE_EMAIL")
        self.assertNotIn(str(twin.id), reasons)
        self.assertEqual(data["summary"]["selected"], 123)
        self.assertEqual(data["summary"]["eligible"], 120)
        self.assertEqual(data["summary"]["skipped"], 3)
        kept = [r["name"] for r in data["recipients"]]
        self.assertIn("Bulk Twin", kept)
        self.assertNotIn("Bulk 000", kept)

    def test_invalid_filters_and_search_are_refused_like_the_list(self):
        cases = [
            ({"filters": [{"field": "bogus", "operator": "equals", "value": "x"}]},
             "Filtering is not supported for field 'bogus'."),
            ({"filters": [{"field": "department", "operator": "weird", "value": "x"}]},
             "Operator 'weird' is not supported"),
            ({"filters": [{"field": "department", "value": "x"}]},
             "Filter at index 0 must contain a valid operator."),
            ({"filters": [{"field": "department", "operator": "equals"}]},
             "Filter at index 0 must contain a value."),
            ({"filters": ["nope"]}, "Filter at index 0 must be a JSON object."),
            ({"filters": {"field": "department"}}, "must be a JSON array"),
            ({"search": "x" * 101}, "Search must be at most 100 characters."),
            ({"search": 12}, "search must be a string or null"),
            ({"exclude_ids": ["not-a-uuid"]}, "exclude_ids must contain valid UUIDs"),
            ({"exclude_ids": "abc"}, "exclude_ids must be a list of ids."),
            ({"exclude_ids": [str(uuid4())] * 2001}, "exclude_ids accepts at most 2000 ids."),
        ]
        for extra, fragment in cases:
            with self.subTest(extra=str(extra)[:60]):
                self.assertDetail400(
                    self.post("contacts", self.filter_selection(**extra)), fragment
                )

    def test_null_search_and_null_filters_mean_none(self):
        response = self.post(
            "contacts", self.filter_selection(search=None, filters=None, exclude_ids=None)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["summary"]["selected"], 121)

    def test_a_search_with_no_match_is_an_empty_success(self):
        response = self.post("contacts", self.filter_selection(search="zzz-nobody"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(
            data["summary"], {"selected": 0, "eligible": 0, "skipped": 0, "batches": 0}
        )
        self.assertEqual((data["recipients"], data["skipped"], data["batches"]), ([], [], []))


class SelectionTooLargeTests(MailRecipientsApiTestCase):
    def test_more_than_2000_matches_is_refused(self):
        bulk_contacts(self.company, self.admin, 2001, "Mass", {})

        response = self.post("contacts", {"mode": "filter", "search": "mass"})
        self.assertDetail400(response, "2001")
        self.assertIn("2000", response.data["detail"])
        self.assertIn("Narrow the search or filters", response.data["detail"])

        # Excluding a few ids does not make the search itself smaller.
        excluded = DjangoContactModel.objects.filter(company=self.company)[:10]
        response = self.post(
            "contacts",
            {"mode": "filter", "search": "mass", "exclude_ids": [str(c.id) for c in excluded]},
        )
        self.assertDetail400(response, "2001")

        # A narrower search over the same data is fine.
        response = self.post(
            "contacts",
            {"mode": "filter", "search": "mass 000"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["summary"]["selected"], 1)


class LeadsTests(MailRecipientsApiTestCase):
    def setUp(self):
        super().setUp()
        self.executive = make_user(self.company, User.Role.SALES_EXECUTIVE)
        self.manager = make_user(self.company, User.Role.SALES_MANAGER)
        self.superadmin = make_user(self.company, User.Role.SUPERADMIN)

        owner = self.admin
        self.ok = make_lead(self.company, owner, "Lee Lead", email="Lee@Lead.test")
        self.no_email = make_lead(self.company, owner, "No Email Lead")
        self.blank_email = make_lead(self.company, owner, "Blank Lead", email="")
        self.bad_email = make_lead(self.company, owner, "Bad Lead", email="nope")
        self.duplicate = make_lead(self.company, owner, "Twin Lead", email="lee@lead.test")
        self.deleted = make_lead(
            self.company, owner, "Gone Lead", email="gone@lead.test", is_deleted=True
        )
        self.converted = make_lead(
            self.company, owner, "Converted Lead", email="conv@lead.test", is_converted=True
        )
        self.foreign = make_lead(
            self.other_company, self.other_admin, "Foreign Lead", email="f@other.test"
        )

    def test_ids_mode_applies_the_lead_rules(self):
        response = self.post(
            "leads",
            {
                "mode": "ids",
                "ids": ids(
                    self.ok, self.no_email, self.blank_email, self.bad_email,
                    self.duplicate, self.deleted, self.foreign,
                ),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        data = response.json()

        self.assertEqual(data["entity"], "leads")
        self.assertEqual(
            data["summary"], {"selected": 7, "eligible": 1, "skipped": 6, "batches": 1}
        )
        self.assertEqual(
            data["recipients"],
            [{
                "record_id": str(self.ok.id), "record_type": "LEAD", "name": "Lee Lead",
                "email": "Lee@Lead.test", "email_kind": "PRIMARY",
                "account_name": None, "source_account_id": None,
            }],
        )
        self.assertEqual(
            [(s["record_type"], s["reason"]) for s in data["skipped"]],
            [("LEAD", "NO_EMAIL"), ("LEAD", "NO_EMAIL"), ("LEAD", "INVALID_EMAIL"),
             ("LEAD", "DUPLICATE_EMAIL"), ("LEAD", "NOT_FOUND"), ("LEAD", "NOT_FOUND")],
        )
        self.assertEqual(data["batches"], [["lee@lead.test"]])

    def test_leads_have_no_opt_out_and_no_secondary_email(self):
        data = self.post(
            "leads", {"mode": "ids", "ids": ids(self.ok)}, include_secondary_email=True
        ).json()
        self.assertEqual([r["email_kind"] for r in data["recipients"]], ["PRIMARY"])
        self.assertNotIn("OPTED_OUT", [s["reason"] for s in data["skipped"]])

    def test_converted_leads_can_be_picked_by_id_like_the_lead_detail(self):
        data = self.post("leads", {"mode": "ids", "ids": ids(self.converted)}).json()
        self.assertEqual([r["email"] for r in data["recipients"]], ["conv@lead.test"])

    def test_filter_mode_uses_the_lead_list_semantics(self):
        # Like the lead list: converted and deleted leads are not in it.
        data = self.post("leads", {"mode": "filter"}).json()
        self.assertEqual(data["summary"]["selected"], 5)  # ok, 3 without usable mail, twin
        returned = {r["record_id"] for r in data["recipients"]} | {
            s["record_id"] for s in data["skipped"]
        }
        self.assertNotIn(str(self.converted.id), returned)
        self.assertNotIn(str(self.deleted.id), returned)
        self.assertNotIn(str(self.foreign.id), returned)

    def test_filter_mode_search_filters_exclude_across_pages(self):
        DjangoLeadModel.objects.bulk_create(
            [
                DjangoLeadModel(
                    company=self.company, owner=self.admin, name=f"Wave {index:03d}",
                    email=f"wave{index:03d}@lead.test",
                    lead_status="Contacted" if index % 3 == 0 else "Not Contacted",
                )
                for index in range(120)
            ],
            batch_size=500,
        )
        data = self.post("leads", {"mode": "filter", "search": "wave"}).json()
        self.assertEqual(data["summary"]["selected"], 120)
        self.assertEqual(data["summary"]["eligible"], 120)
        self.assertEqual([len(b) for b in data["batches"]], [40, 40, 40])

        filters = [{"field": "lead_status", "operator": "equals", "value": "Contacted"}]
        data = self.post("leads", {"mode": "filter", "search": "wave", "filters": filters}).json()
        self.assertEqual(data["summary"]["selected"], 40)

        excluded = DjangoLeadModel.objects.filter(
            company=self.company, name__in=["Wave 000", "Wave 003"]
        )
        data = self.post(
            "leads",
            {"mode": "filter", "search": "wave", "filters": filters,
             "exclude_ids": [str(lead.id) for lead in excluded]},
        ).json()
        self.assertEqual(data["summary"]["selected"], 38)

    def test_filter_mode_refuses_bad_lead_filters(self):
        response = self.post(
            "leads",
            {"mode": "filter",
             "filters": [{"field": "bogus", "operator": "equals", "value": "x"}]},
        )
        self.assertDetail400(response)

    def test_role_rules_follow_the_lead_screens(self):
        filter_selection = {"mode": "filter"}
        ids_selection = {"mode": "ids", "ids": ids(self.ok)}

        # Filter mode = the lead list: admins only.
        for user, expected in (
            (self.admin, status.HTTP_200_OK),
            (self.superadmin, status.HTTP_200_OK),
            (self.manager, status.HTTP_403_FORBIDDEN),
            (self.executive, status.HTTP_403_FORBIDDEN),
        ):
            with self.subTest(mode="filter", role=user.role):
                response = self.post("leads", filter_selection, client=authenticated_client(user))
                self.assertEqual(response.status_code, expected)
                if expected == status.HTTP_403_FORBIDDEN:
                    self.assertEqual(set(response.data), {"detail"})

        # Ids mode = the lead detail: any company user.
        for user in (self.admin, self.superadmin, self.manager, self.executive):
            with self.subTest(mode="ids", role=user.role):
                response = self.post("leads", ids_selection, client=authenticated_client(user))
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(len(response.json()["recipients"]), 1)

    def test_contacts_and_accounts_are_open_to_every_company_user(self):
        executive_client = authenticated_client(self.executive)
        for entity in ("contacts", "accounts"):
            with self.subTest(entity=entity):
                response = self.post(entity, {"mode": "filter"}, client=executive_client)
                self.assertEqual(response.status_code, status.HTTP_200_OK)


class AccountsTests(MailRecipientsApiTestCase):
    def setUp(self):
        super().setUp()
        owner = self.admin
        self.alpha = make_account(self.company, owner, "Alpha Inc")
        self.beta = make_account(self.company, owner, "Beta LLC")  # no contacts
        self.gone = make_account(self.company, owner, "Gone Corp", is_deleted=True)
        self.foreign = make_account(self.other_company, self.other_admin, "Foreign Corp")

        self.ok = make_contact(
            self.company, owner, "A1 Ok", account=self.alpha,
            email="a1@alpha.test", secondary_email="a1.alt@alpha.test",
        )
        self.opted_out = make_contact(
            self.company, owner, "A2 Opted", account=self.alpha,
            email="a2@alpha.test", email_opt_out=True,
        )
        self.no_email = make_contact(self.company, owner, "A3 NoMail", account=self.alpha)
        self.deleted_contact = make_contact(
            self.company, owner, "A4 Deleted", account=self.alpha,
            email="gone@alpha.test", is_deleted=True,
        )
        make_contact(
            self.other_company, self.other_admin, "Foreign Contact", account=self.foreign,
            email="foreign@other.test",
        )

    def test_ids_mode_resolves_accounts_to_their_contacts(self):
        response = self.post(
            "accounts",
            {"mode": "ids", "ids": ids(self.alpha, self.beta, self.gone, self.foreign)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        data = response.json()

        self.assertEqual(data["entity"], "accounts")
        self.assertEqual(
            data["summary"], {"selected": 4, "eligible": 1, "skipped": 5, "batches": 1}
        )
        self.assertEqual(
            data["recipients"],
            [{
                "record_id": str(self.ok.id), "record_type": "CONTACT", "name": "A1 Ok",
                "email": "a1@alpha.test", "email_kind": "PRIMARY",
                "account_name": "Alpha Inc", "source_account_id": str(self.alpha.id),
            }],
        )
        self.assertEqual(
            data["skipped"],
            [
                {"record_id": str(self.opted_out.id), "record_type": "CONTACT",
                 "name": "A2 Opted", "reason": "OPTED_OUT"},
                {"record_id": str(self.no_email.id), "record_type": "CONTACT",
                 "name": "A3 NoMail", "reason": "NO_EMAIL"},
                {"record_id": str(self.beta.id), "record_type": "ACCOUNT",
                 "name": "Beta LLC", "reason": "NO_CONTACTS"},
                {"record_id": str(self.gone.id), "record_type": "ACCOUNT",
                 "name": "", "reason": "NOT_FOUND"},
                {"record_id": str(self.foreign.id), "record_type": "ACCOUNT",
                 "name": "", "reason": "NOT_FOUND"},
            ],
        )
        self.assertEqual(data["batches"], [["a1@alpha.test"]])
        self.assertNotIn("gone@alpha.test", json.dumps(data))  # soft-deleted contact
        self.assertNotIn("foreign@other.test", json.dumps(data))

    def test_secondary_email_of_account_contacts(self):
        data = self.post(
            "accounts", {"mode": "ids", "ids": ids(self.alpha)}, include_secondary_email=True
        ).json()
        self.assertEqual(
            [(r["email"], r["email_kind"], r["source_account_id"]) for r in data["recipients"]],
            [("a1@alpha.test", "PRIMARY", str(self.alpha.id)),
             ("a1.alt@alpha.test", "SECONDARY", str(self.alpha.id))],
        )

    def test_a_contact_shared_by_two_selected_accounts_is_not_duplicated(self):
        second = make_account(self.company, self.admin, "Alpha Two")
        make_contact(
            self.company, self.admin, "Same Address", account=second, email="A1@ALPHA.test"
        )
        data = self.post("accounts", {"mode": "ids", "ids": ids(self.alpha, second)}).json()
        self.assertEqual(len(data["recipients"]), 1)
        self.assertIn(
            ("CONTACT", "DUPLICATE_EMAIL"),
            [(s["record_type"], s["reason"]) for s in data["skipped"]],
        )

    def test_filter_mode_over_more_than_one_page_of_accounts(self):
        now = timezone.now()
        accounts = []
        for index in range(60):
            account = make_account(
                self.company, self.admin, f"Mass Co {index:03d}",
                created_at=now + timedelta(seconds=index),
            )
            make_contact(
                self.company, self.admin, f"Mass Person {index:03d}", account=account,
                email=f"person{index:03d}@mass-co.test",
            )
            accounts.append(account)
        make_account(self.company, self.admin, "Mass Co Empty",
                     created_at=now + timedelta(seconds=100))

        data = self.post(
            "accounts", {"mode": "filter", "search": "mass co"}, batch_size=50
        ).json()
        self.assertEqual(data["summary"]["selected"], 61)
        self.assertEqual(data["summary"]["eligible"], 60)
        self.assertEqual(
            [(s["record_type"], s["reason"], s["name"]) for s in data["skipped"]],
            [("ACCOUNT", "NO_CONTACTS", "Mass Co Empty")],
        )
        self.assertEqual([len(b) for b in data["batches"]], [50, 10])
        self.assertTrue(all(r["source_account_id"] for r in data["recipients"]))

        data = self.post(
            "accounts",
            {"mode": "filter", "search": "mass co",
             "exclude_ids": ids(accounts[0], accounts[59])},
        ).json()
        self.assertEqual(data["summary"]["selected"], 59)
        self.assertEqual(data["summary"]["eligible"], 58)

    def test_filter_mode_accepts_account_filters(self):
        filters = [{"field": "account_name", "operator": "starts_with", "value": "Alpha"}]
        data = self.post("accounts", {"mode": "filter", "filters": filters}).json()
        self.assertEqual(data["summary"]["selected"], 1)

        bad = [{"field": "bogus", "operator": "equals", "value": "x"}]
        self.assertDetail400(self.post("accounts", {"mode": "filter", "filters": bad}))

    def test_filter_mode_never_includes_other_companies_or_deleted_accounts(self):
        data = self.post("accounts", {"mode": "filter"}).json()
        names = {r["account_name"] for r in data["recipients"]}
        self.assertEqual(names, {"Alpha Inc"})
        self.assertEqual(data["summary"]["selected"], 2)  # Alpha Inc + Beta LLC


class AccessAndValidationTests(MailRecipientsApiTestCase):
    def test_unauthenticated_is_401(self):
        response = APIClient().post(
            URL,
            {"entity": "contacts", "selection": {"mode": "ids", "ids": [str(uuid4())]}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_platform_superadmin_has_no_company_and_is_refused(self):
        platform = make_user(None, User.Role.PLATFORM_SUPERADMIN)
        response = self.post(
            "contacts",
            {"mode": "ids", "ids": [str(uuid4())]},
            client=authenticated_client(platform),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_only_post_is_allowed(self):
        self.assertEqual(self.client.get(URL).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_more_than_500_ids_is_a_400(self):
        response = self.post(
            "contacts", {"mode": "ids", "ids": [str(uuid4()) for _ in range(501)]}
        )
        self.assertDetail400(response, "at most 500 ids")

    def test_invalid_requests_are_400_with_a_detail(self):
        valid_ids = {"mode": "ids", "ids": [str(uuid4())]}
        cases = [
            ("missing entity", {"selection": valid_ids}, "entity"),
            ("unknown entity", {"entity": "tasks", "selection": valid_ids},
             "entity must be one of: contacts, leads, accounts."),
            ("missing selection", {"entity": "contacts"}, "selection"),
            ("selection not an object", {"entity": "contacts", "selection": "all"},
             "selection must be an object."),
            ("missing mode", {"entity": "contacts", "selection": {"ids": [str(uuid4())]}},
             "selection.mode must be 'ids' or 'filter'."),
            ("unknown mode", {"entity": "contacts", "selection": {"mode": "all"}},
             "selection.mode must be 'ids' or 'filter'."),
            ("ids missing", {"entity": "contacts", "selection": {"mode": "ids"}},
             "ids must be a list of ids."),
            ("ids not a list", {"entity": "contacts", "selection": {"mode": "ids", "ids": "x"}},
             "ids must be a list of ids."),
            ("ids empty", {"entity": "contacts", "selection": {"mode": "ids", "ids": []}},
             "ids must contain at least one id."),
            ("ids not uuids",
             {"entity": "contacts", "selection": {"mode": "ids", "ids": [str(uuid4()), "42"]}},
             "ids must contain valid UUIDs (invalid value at index 1)."),
            ("ids not strings",
             {"entity": "contacts", "selection": {"mode": "ids", "ids": [123]}},
             "ids must contain valid UUIDs"),
            ("batch_size zero", {"entity": "contacts", "selection": valid_ids, "batch_size": 0},
             "batch_size must be between 1 and 50."),
            ("batch_size 51", {"entity": "contacts", "selection": valid_ids, "batch_size": 51},
             "batch_size must be between 1 and 50."),
            ("batch_size text", {"entity": "contacts", "selection": valid_ids, "batch_size": "many"},
             "batch_size must be a whole number."),
            ("body is a list", [1, 2], "Invalid data"),
        ]
        for label, payload, fragment in cases:
            with self.subTest(label):
                response = self.client.post(URL, payload, format="json")
                self.assertDetail400(response, fragment)

    def test_defaults_are_40_and_no_secondary_email(self):
        contact = make_contact(
            self.company, self.admin, "Solo", email="solo@x.test",
            secondary_email="solo.alt@x.test",
        )
        data = self.post("contacts", {"mode": "ids", "ids": ids(contact)}).json()
        self.assertEqual([r["email_kind"] for r in data["recipients"]], ["PRIMARY"])

        bulk = bulk_contacts(self.company, self.admin, 41, "Default", {})
        data = self.post("contacts", {"mode": "ids", "ids": ids(*bulk)}).json()
        self.assertEqual([len(b) for b in data["batches"]], [40, 1])

    def test_malformed_emails_are_never_sent_to_a_batch(self):
        # Anything that could break out of a Bcc header must be INVALID_EMAIL.
        bad = [
            "a@x.test,b@y.test",
            "a@x.test; b@y.test",
            "a@x.test\nBcc: evil@z.test",
            "Name <a@x.test>",
            "a b@x.test",
            "@x.test",
            "a@",
        ]
        contacts = [
            make_contact(self.company, self.admin, f"Evil {index}", email=email)
            for index, email in enumerate(bad)
        ]
        data = self.post("contacts", {"mode": "ids", "ids": ids(*contacts)}).json()
        self.assertEqual(data["recipients"], [])
        self.assertEqual(data["batches"], [])
        self.assertEqual({s["reason"] for s in data["skipped"]}, {"INVALID_EMAIL"})


class GetManyByIdsRepositoryTests(TestCase):
    """The new repository method: company scoped, no soft-deleted, ONE query."""

    def setUp(self):
        self.company = make_company("Repo Co")
        self.other_company = make_company("Repo Other Co")
        self.owner = make_user(self.company, User.Role.ADMIN)
        self.other_owner = make_user(self.other_company, User.Role.ADMIN)

    def test_contacts(self):
        mine = make_contact(self.company, self.owner, "Mine", email="m@x.test")
        mine_too = make_contact(self.company, self.owner, "Mine Too")
        deleted = make_contact(self.company, self.owner, "Deleted", is_deleted=True)
        foreign = make_contact(self.other_company, self.other_owner, "Foreign")
        repository = DjangoContactRepository(company_id=self.company.id)

        with self.assertNumQueries(1):
            found = repository.get_many_by_ids(
                [mine.id, mine_too.id, deleted.id, foreign.id, uuid4()]
            )
        self.assertEqual({c.id for c in found}, {mine.id, mine_too.id})
        self.assertEqual(
            {c.id: c.email for c in found}[mine.id], "m@x.test"
        )
        with self.assertNumQueries(0):
            self.assertEqual(repository.get_many_by_ids([]), [])

    def test_leads(self):
        mine = make_lead(self.company, self.owner, "Mine", email="m@x.test")
        converted = make_lead(self.company, self.owner, "Converted", is_converted=True)
        deleted = make_lead(self.company, self.owner, "Deleted", is_deleted=True)
        foreign = make_lead(self.other_company, self.other_owner, "Foreign")
        repository = DjangoLeadRepository(company_id=self.company.id)

        with self.assertNumQueries(1):
            found = repository.get_many_by_ids(
                [mine.id, converted.id, deleted.id, foreign.id, uuid4()]
            )
        self.assertEqual({lead.id for lead in found}, {mine.id, converted.id})
        with self.assertNumQueries(0):
            self.assertEqual(repository.get_many_by_ids([]), [])

    def test_accounts(self):
        mine = make_account(self.company, self.owner, "Mine")
        deleted = make_account(self.company, self.owner, "Deleted", is_deleted=True)
        foreign = make_account(self.other_company, self.other_owner, "Foreign")
        repository = DjangoAccountRepository(company_id=self.company.id)

        with self.assertNumQueries(1):
            found = repository.get_many_by_ids([mine.id, deleted.id, foreign.id, uuid4()])
        self.assertEqual([a.id for a in found], [mine.id])
        self.assertEqual(found[0].account_name, "Mine")
        with self.assertNumQueries(0):
            self.assertEqual(repository.get_many_by_ids([]), [])

    def test_ports_have_a_non_abstract_default_that_raises(self):
        for port in (ContactRepository, LeadRepository, AccountRepository):
            with self.subTest(port=port.__name__):
                self.assertNotIn("get_many_by_ids", port.__abstractmethods__)
                with self.assertRaises(NotImplementedError):
                    port.get_many_by_ids(object(), [])
