"""Converted import rows are written in bulk chunks, with a row-by-row fallback.

No database: the repositories and the transaction manager are small fakes.
"""

from uuid import UUID, uuid4

from django.test import SimpleTestCase

from src.modules.leads.application.services import lead_import_conversion as conv
from src.modules.leads.application.services.lead_import_conversion import (
    ConversionContext,
    convert_outcomes,
)
from src.modules.leads.application.services.lead_import_options import ImportOptions
from src.modules.leads.application.services.lead_import_pipeline import CONVERT, RowOutcome
from src.modules.leads.domain.entities.lead import Lead

OWNER = UUID(int=1)
ACTOR = UUID(int=2)


class FakeLeadRepo:
    def __init__(self):
        self.rows = {}
        self.bulk_calls = 0

    def bulk_create_for_import(self, leads, job_id):
        self.bulk_calls += 1
        for lead in leads:
            self.rows[lead.id] = lead
        return len(leads)

    def save(self, lead):
        self.rows[lead.id] = lead
        return lead


class FakeAccountRepo:
    def __init__(self):
        self.rows = {}
        self.bulk_calls = 0

    def find_for_import_matching(self, names, sites):
        return []

    def bulk_create_for_import(self, accounts):
        self.bulk_calls += 1
        for account in accounts:
            self.rows[account.id] = account
        return len(accounts)

    def save(self, account):
        self.rows[account.id] = account
        return account


class FakeContactRepo:
    def __init__(self, existing=()):
        self.rows = {c.id: c for c in existing}
        self.existing = list(existing)
        self.bulk_calls = 0
        self.fail_bulk_on = None  # a contact name that makes a bulk insert fail
        self.links = {}

    def find_for_import_matching(self, emails, endings):
        return list(self.existing)

    def bulk_create_for_import(self, contacts):
        self.bulk_calls += 1
        for contact in contacts:
            if contact.name == self.fail_bulk_on:
                raise RuntimeError("database refused the chunk")
        for contact in contacts:
            self.rows[contact.id] = contact
        return len(contacts)

    def bulk_set_account_for_import(self, links):
        self.links.update(links)
        return len(links)

    def save(self, contact):
        if contact.name == self.fail_bulk_on and contact.id not in self.rows:
            raise RuntimeError("database refused the contact")
        self.rows[contact.id] = contact
        return contact


class RollbackTransactionManager:
    """Undoes what the fake repositories stored when the operation raises."""

    def __init__(self, *repos):
        self.repos = repos

    def execute(self, operation):
        before = [dict(r.rows) for r in self.repos]
        try:
            return operation()
        except Exception:
            for repo, rows in zip(self.repos, before):
                repo.rows = rows
            raise


def build_lead(outcome):
    data = outcome.payload
    return Lead.create(
        name=data["name"], title=None, company_name=data.get("company_name"),
        email=data.get("email"), mobile_number=None, phone=data.get("phone"),
        lead_source="None", lead_status="None", industry="None", rating="None",
        website=None, number_of_employees=None, annual_revenue=None,
        owner_id=OWNER, address=None, city=None, state=None, country=None,
        postal_code=None, description=None,
    )


def outcome(n, name, company=None, email=None):
    return RowOutcome(
        row_number=n, status=CONVERT, is_converted=True, owner_id=str(OWNER),
        payload={"name": name, "company_name": company, "email": email},
    )


def make(contact_repo=None, **options):
    leads, accounts = FakeLeadRepo(), FakeAccountRepo()
    contacts = contact_repo or FakeContactRepo()
    context = ConversionContext(
        options=ImportOptions.from_dict(options),
        actor_id=ACTOR,
        lead_repository=leads,
        account_repository=accounts,
        contact_repository=contacts,
        transaction_manager=RollbackTransactionManager(leads, accounts, contacts),
        build_lead=build_lead,
    )
    return context, leads, accounts, contacts


class BulkConversionTests(SimpleTestCase):
    def test_many_rows_use_a_few_bulk_writes_not_one_write_per_row(self):
        context, leads, accounts, contacts = make()
        rows = [outcome(i, f"Person {i}", company=f"Co {i}", email=f"p{i}@x.com") for i in range(120)]
        result = convert_outcomes(SimpleJob(), rows, context)

        self.assertEqual(len(result.converted), 120)
        self.assertEqual(result.failed, [])
        self.assertEqual(len(leads.rows), 120)
        self.assertTrue(all(lead.is_converted for lead in leads.rows.values()))
        self.assertEqual(len(accounts.rows), 120)
        self.assertEqual(len(contacts.rows), 120)
        # 120 rows = 3 chunks of 50/50/20: one insert per table per chunk.
        self.assertEqual(leads.bulk_calls, 3)
        self.assertEqual(accounts.bulk_calls, 3)
        self.assertEqual(contacts.bulk_calls, 3)

    def test_same_company_in_one_chunk_creates_one_account(self):
        context, _leads, accounts, contacts = make()
        rows = [outcome(i, f"Person {i}", company="Acme Ltd", email=f"p{i}@x.com") for i in range(10)]
        result = convert_outcomes(SimpleJob(), rows, context)

        self.assertEqual(len(result.converted), 10)
        self.assertEqual(len(accounts.rows), 1)
        self.assertEqual(len(result.created_accounts), 1)
        self.assertEqual(len(result.reused_accounts), 0)  # created by this import
        account_id = next(iter(accounts.rows))
        self.assertTrue(all(c.account_id == account_id for c in contacts.rows.values()))

    def test_create_new_makes_an_account_per_row(self):
        context, _l, accounts, _c = make(account_match="create_new")
        rows = [outcome(i, f"P{i}", company="Acme Ltd") for i in range(3)]
        convert_outcomes(SimpleJob(), rows, context)
        self.assertEqual(len(accounts.rows), 3)

    def test_a_row_without_a_company_becomes_a_contact_only(self):
        context, _l, accounts, contacts = make()
        result = convert_outcomes(SimpleJob(), [outcome(1, "Solo")], context)
        self.assertEqual(result.converted, [1])
        self.assertEqual(len(accounts.rows), 0)
        self.assertIsNone(next(iter(contacts.rows.values())).account_id)

    def test_a_row_that_cannot_be_built_fails_alone(self):
        context, leads, _a, _c = make()
        good, bad = outcome(1, "Good", company="A"), outcome(2, "Bad", company="B")
        bad.owner_id = None
        bad.payload["__no_owner__"] = True

        def builder(o):
            return None if o.payload.get("__no_owner__") else build_lead(o)

        context.build_lead = builder
        result = convert_outcomes(SimpleJob(), [good, bad], context)

        self.assertEqual(result.converted, [1])
        self.assertEqual([o.row_number for o in result.failed], [2])
        self.assertEqual(result.failed[0].status, "error")
        self.assertIn("no owner", result.failed[0].problems[0].message)
        self.assertEqual(len(leads.rows), 1)

    def test_a_failed_bulk_write_falls_back_to_rows_and_only_the_bad_row_fails(self):
        contacts = FakeContactRepo()
        contacts.fail_bulk_on = "Broken"
        context, leads, accounts, contacts = make(contact_repo=contacts)
        rows = [
            outcome(1, "Fine One", company="A", email="a@x.com"),
            outcome(2, "Broken", company="B", email="b@x.com"),
            outcome(3, "Fine Two", company="C", email="c@x.com"),
        ]
        result = convert_outcomes(SimpleJob(), rows, context)

        self.assertEqual(sorted(result.converted), [1, 3])
        self.assertEqual([o.row_number for o in result.failed], [2])
        self.assertIn("row 2", result.failed[0].problems[0].message)
        # Nothing of the bad row stays behind; the good rows are complete.
        self.assertEqual(len(leads.rows), 2)
        self.assertEqual({a.account_name for a in accounts.rows.values()}, {"A", "C"})
        self.assertEqual({c.name for c in contacts.rows.values()}, {"Fine One", "Fine Two"})

    def test_a_bad_chunk_does_not_slow_the_next_chunk(self):
        contacts = FakeContactRepo()
        contacts.fail_bulk_on = "Broken"
        context, leads, _a, contacts = make(contact_repo=contacts)
        rows = [outcome(i, f"P{i}", company=f"Co{i}") for i in range(1, 61)]
        rows[0] = outcome(1, "Broken", company="Co1")
        result = convert_outcomes(SimpleJob(), rows, context)

        self.assertEqual(len(result.converted), 59)
        self.assertEqual(len(result.failed), 1)
        # Chunk 1 (rows 1-50): the failed bulk write, then 50 single-row writes.
        # Chunk 2 (rows 51-60) goes back to ONE bulk write: 1 + 50 + 1 calls.
        self.assertEqual(leads.bulk_calls, 52)

    def test_existing_contact_without_an_account_is_attached(self):
        from src.modules.contacts.domain.entities.contact import Contact

        existing = Contact.create(
            account_id=None, contact_owner_id=OWNER, name="Old Contact",
            email="old@x.com", secondary_email=None, phone=None, other_phone=None,
            mobile=None, home_phone=None, assistant_phone=None, title=None,
            department=None, lead_source="None", vendor_name=None, date_of_birth=None,
            assistant=None, email_opt_out=False, reporting_to_id=None,
            mailing_address=None, mailing_city=None, mailing_state=None,
            mailing_country=None, mailing_postal_code=None, other_address=None,
            description=None, created_by_id=ACTOR,
        )
        context, _l, accounts, contacts = make(contact_repo=FakeContactRepo([existing]))
        result = convert_outcomes(
            SimpleJob(), [outcome(1, "Whoever", company="Acme", email="old@x.com")], context
        )

        self.assertEqual(result.converted, [1])
        self.assertEqual(result.reused_contacts, [str(existing.id)])
        self.assertEqual(result.created_contacts, [])
        account_id = next(iter(accounts.rows))
        self.assertEqual(contacts.links, {existing.id: account_id})
        self.assertIsNone(existing.account_id)  # the cached original is untouched


class SimpleJob:
    id = uuid4()
