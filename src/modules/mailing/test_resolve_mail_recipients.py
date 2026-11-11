import ast
import pathlib
from uuid import uuid4

from django.test import SimpleTestCase

from src.modules.mailing.application.dto.limits import (
    MAX_EXCLUDE_IDS,
    MAX_FILTER_MATCHES,
    MAX_IDS,
)
from src.modules.mailing.application.dto.resolve_recipients import (
    FilterSelection,
    FilterSpec,
    IdsSelection,
    MailTarget,
    ResolveRecipientsCommand,
    SourceRecord,
)
from src.modules.mailing.application.interfaces.recipient_source import (
    SelectionTooLargeError,
)
from src.modules.mailing.application.services.recipient_rules import (
    EmailRegistry,
    check_email,
    chunk,
    validate_batch_size,
)
from src.modules.mailing.application.use_cases.resolve_mail_recipients import (
    ResolveMailRecipientsUseCase,
)
from src.modules.mailing.domain.enums.email_kind import EmailKind
from src.modules.mailing.domain.enums.mail_entity import MailEntity
from src.modules.mailing.domain.enums.record_type import RecordType
from src.modules.mailing.domain.enums.skip_reason import SkipReason


def fake_is_valid(address: str) -> bool:
    """Stand-in for Django's validate_email (the use case never imports it)."""
    local, _, domain = address.partition("@")
    return bool(local) and "." in domain and " " not in address and "," not in address


def contact_record(
    name="Ann",
    email="ann@x.com",
    secondary=None,
    opt_out=False,
    account_name=None,
    source_account_id=None,
    record_id=None,
) -> SourceRecord:
    record_id = record_id or uuid4()
    return SourceRecord(
        record_id=record_id,
        record_type=RecordType.CONTACT,
        name=name,
        targets=(
            MailTarget(
                record_id=record_id,
                record_type=RecordType.CONTACT,
                name=name,
                email=email,
                secondary_email=secondary,
                email_opt_out=opt_out,
                account_name=account_name,
                source_account_id=source_account_id,
            ),
        ),
    )


def lead_record(name="Lee", email="lee@x.com", record_id=None) -> SourceRecord:
    record_id = record_id or uuid4()
    return SourceRecord(
        record_id=record_id,
        record_type=RecordType.LEAD,
        name=name,
        targets=(
            MailTarget(
                record_id=record_id,
                record_type=RecordType.LEAD,
                name=name,
                email=email,
            ),
        ),
    )


def account_record(name="Acme", contacts=(), record_id=None) -> SourceRecord:
    record_id = record_id or uuid4()
    targets = []
    for contact_name, email, secondary, opt_out in contacts:
        targets.append(
            MailTarget(
                record_id=uuid4(),
                record_type=RecordType.CONTACT,
                name=contact_name,
                email=email,
                secondary_email=secondary,
                email_opt_out=opt_out,
                account_name=name,
                source_account_id=record_id,
            )
        )
    return SourceRecord(
        record_id=record_id,
        record_type=RecordType.ACCOUNT,
        name=name,
        targets=tuple(targets),
    )


class FakeSource:
    """In-memory RecipientSource."""

    def __init__(self, entity, record_type, records=()):
        self.entity = entity
        self.record_type = record_type
        self.records = list(records)
        self.id_calls = []
        self.match_calls = []

    def get_by_ids(self, ids):
        self.id_calls.append(list(ids))
        wanted = set(ids)
        # Deliberately NOT in requested order.
        return [r for r in reversed(self.records) if r.record_id in wanted]

    def get_matching(self, search, filters, max_matches):
        self.match_calls.append((search, tuple(filters), max_matches))
        if len(self.records) > max_matches:
            raise SelectionTooLargeError(f"{len(self.records)} > {max_matches}")
        return list(self.records)


def contacts_source(*records):
    return FakeSource(MailEntity.CONTACTS, RecordType.CONTACT, records)


def leads_source(*records):
    return FakeSource(MailEntity.LEADS, RecordType.LEAD, records)


def accounts_source(*records):
    return FakeSource(MailEntity.ACCOUNTS, RecordType.ACCOUNT, records)


def run(source, ids=None, *, include_secondary=False, batch_size=40, selection=None):
    selection = selection or IdsSelection(
        ids=tuple(ids if ids is not None else [r.record_id for r in source.records])
    )
    return ResolveMailRecipientsUseCase(source, fake_is_valid).execute(
        ResolveRecipientsCommand(
            selection=selection,
            include_secondary_email=include_secondary,
            batch_size=batch_size,
        )
    )


def reasons(result):
    return [s.reason for s in result.skipped]


class ContactRulesTests(SimpleTestCase):
    def test_eligible_contact_becomes_a_primary_recipient(self):
        record = contact_record("Ann", "Ann@X.com", account_name="Acme")
        result = run(contacts_source(record))

        self.assertEqual(result.entity, MailEntity.CONTACTS)
        self.assertEqual(result.selected, 1)
        [recipient] = result.recipients
        self.assertEqual(recipient.record_id, record.record_id)
        self.assertEqual(recipient.record_type, RecordType.CONTACT)
        self.assertEqual(recipient.name, "Ann")
        self.assertEqual(recipient.email, "Ann@X.com")  # shown as stored
        self.assertEqual(recipient.email_kind, EmailKind.PRIMARY)
        self.assertEqual(recipient.account_name, "Acme")
        self.assertIsNone(recipient.source_account_id)
        self.assertEqual(result.batches, [["ann@x.com"]])  # sent lower-cased
        self.assertEqual(result.skipped, [])

    def test_opted_out_contact_is_skipped(self):
        result = run(contacts_source(contact_record(opt_out=True)))
        self.assertEqual(result.recipients, [])
        self.assertEqual(reasons(result), [SkipReason.OPTED_OUT])
        self.assertEqual(result.skipped[0].record_type, RecordType.CONTACT)

    def test_opt_out_wins_over_a_missing_email(self):
        result = run(contacts_source(contact_record(email=None, opt_out=True)))
        self.assertEqual(reasons(result), [SkipReason.OPTED_OUT])

    def test_missing_email_is_no_email(self):
        for missing in (None, "", "   "):
            with self.subTest(email=missing):
                result = run(contacts_source(contact_record(email=missing)))
                self.assertEqual(result.recipients, [])
                self.assertEqual(reasons(result), [SkipReason.NO_EMAIL])

    def test_malformed_email_is_invalid_email(self):
        for bad in ("not-an-email", "a@b", "two words@x.com", "a@x.com,b@y.com"):
            with self.subTest(email=bad):
                result = run(contacts_source(contact_record(email=bad)))
                self.assertEqual(result.recipients, [])
                self.assertEqual(reasons(result), [SkipReason.INVALID_EMAIL])

    def test_surrounding_blanks_are_trimmed(self):
        result = run(contacts_source(contact_record(email="  ann@x.com ")))
        self.assertEqual(result.recipients[0].email, "ann@x.com")

    def test_secondary_email_is_ignored_unless_asked_for(self):
        record = contact_record(secondary="alt@x.com")
        result = run(contacts_source(record), include_secondary=False)
        self.assertEqual([r.email for r in result.recipients], ["ann@x.com"])

    def test_secondary_email_is_an_extra_recipient_when_asked_for(self):
        record = contact_record(secondary="Alt@X.com", account_name="Acme")
        result = run(contacts_source(record), include_secondary=True)

        self.assertEqual(
            [(r.email, r.email_kind) for r in result.recipients],
            [("ann@x.com", EmailKind.PRIMARY), ("Alt@X.com", EmailKind.SECONDARY)],
        )
        self.assertTrue(all(r.record_id == record.record_id for r in result.recipients))
        self.assertEqual(result.recipients[1].account_name, "Acme")
        self.assertEqual(result.batches, [["ann@x.com", "alt@x.com"]])
        self.assertEqual(result.selected, 1)

    def test_missing_or_malformed_secondary_is_ignored_silently(self):
        for secondary in (None, "", "garbage"):
            with self.subTest(secondary=secondary):
                result = run(
                    contacts_source(contact_record(secondary=secondary)),
                    include_secondary=True,
                )
                self.assertEqual(len(result.recipients), 1)
                self.assertEqual(result.skipped, [])

    def test_valid_secondary_still_used_when_primary_is_unusable(self):
        record = contact_record(email=None, secondary="alt@x.com")
        result = run(contacts_source(record), include_secondary=True)

        self.assertEqual([r.email_kind for r in result.recipients], [EmailKind.SECONDARY])
        self.assertEqual(reasons(result), [SkipReason.NO_EMAIL])

    def test_opt_out_blocks_the_secondary_email_too(self):
        record = contact_record(secondary="alt@x.com", opt_out=True)
        result = run(contacts_source(record), include_secondary=True)
        self.assertEqual(result.recipients, [])
        self.assertEqual(reasons(result), [SkipReason.OPTED_OUT])

    def test_secondary_equal_to_primary_is_a_duplicate(self):
        record = contact_record(email="a@x.com", secondary="A@X.com")
        result = run(contacts_source(record), include_secondary=True)
        self.assertEqual(len(result.recipients), 1)
        self.assertEqual(reasons(result), [SkipReason.DUPLICATE_EMAIL])


class LeadRulesTests(SimpleTestCase):
    def test_lead_with_a_valid_email_is_a_lead_recipient(self):
        record = lead_record("Lee", "lee@x.com")
        result = run(leads_source(record))
        self.assertEqual(result.entity, MailEntity.LEADS)
        [recipient] = result.recipients
        self.assertEqual(recipient.record_type, RecordType.LEAD)
        self.assertEqual(recipient.email_kind, EmailKind.PRIMARY)
        self.assertIsNone(recipient.account_name)
        self.assertIsNone(recipient.source_account_id)

    def test_lead_without_or_with_bad_email_is_skipped(self):
        source = leads_source(
            lead_record("None", None),
            lead_record("Blank", " "),
            lead_record("Bad", "nope"),
        )
        result = run(source)
        self.assertEqual(
            reasons(result),
            [SkipReason.NO_EMAIL, SkipReason.NO_EMAIL, SkipReason.INVALID_EMAIL],
        )
        self.assertTrue(all(s.record_type == RecordType.LEAD for s in result.skipped))


class AccountRulesTests(SimpleTestCase):
    def test_account_resolves_to_its_contacts_with_source_account_id(self):
        account = account_record(
            "Acme",
            contacts=[
                ("Ann", "ann@x.com", None, False),
                ("Bob", "bob@x.com", None, False),
            ],
        )
        result = run(accounts_source(account))

        self.assertEqual(result.entity, MailEntity.ACCOUNTS)
        self.assertEqual(result.selected, 1)  # one selected account
        self.assertEqual([r.name for r in result.recipients], ["Ann", "Bob"])
        for recipient in result.recipients:
            self.assertEqual(recipient.record_type, RecordType.CONTACT)
            self.assertEqual(recipient.source_account_id, account.record_id)
            self.assertEqual(recipient.account_name, "Acme")

    def test_account_without_contacts_is_no_contacts(self):
        account = account_record("Empty")
        result = run(accounts_source(account))
        self.assertEqual(result.recipients, [])
        [skip] = result.skipped
        self.assertEqual(skip.reason, SkipReason.NO_CONTACTS)
        self.assertEqual(skip.record_type, RecordType.ACCOUNT)
        self.assertEqual(skip.record_id, account.record_id)
        self.assertEqual(skip.name, "Empty")

    def test_contact_rules_apply_to_account_contacts(self):
        account = account_record(
            "Acme",
            contacts=[
                ("Opted", "o@x.com", None, True),
                ("Missing", None, None, False),
                ("Broken", "broken", None, False),
                ("Fine", "fine@x.com", "alt@x.com", False),
            ],
        )
        result = run(accounts_source(account), include_secondary=True)

        self.assertEqual(
            [(r.name, r.email_kind) for r in result.recipients],
            [("Fine", EmailKind.PRIMARY), ("Fine", EmailKind.SECONDARY)],
        )
        self.assertEqual(
            reasons(result),
            [SkipReason.OPTED_OUT, SkipReason.NO_EMAIL, SkipReason.INVALID_EMAIL],
        )
        # The skipped entries are about the contacts, not the account.
        self.assertTrue(all(s.record_type == RecordType.CONTACT for s in result.skipped))

    def test_account_whose_contacts_are_all_skipped_is_not_no_contacts(self):
        account = account_record("Acme", contacts=[("Opted", "o@x.com", None, True)])
        result = run(accounts_source(account))
        self.assertEqual(reasons(result), [SkipReason.OPTED_OUT])

    def test_same_address_in_two_accounts_is_a_duplicate(self):
        first = account_record("A", contacts=[("Ann", "shared@x.com", None, False)])
        second = account_record("B", contacts=[("Bob", "SHARED@x.com", None, False)])
        result = run(accounts_source(first, second))
        self.assertEqual([r.name for r in result.recipients], ["Ann"])
        self.assertEqual(reasons(result), [SkipReason.DUPLICATE_EMAIL])
        self.assertEqual(result.skipped[0].name, "Bob")


class DeduplicationTests(SimpleTestCase):
    def test_duplicates_are_case_insensitive_and_the_first_is_kept(self):
        first = contact_record("First", "Dup@X.com")
        second = contact_record("Second", "dup@x.com")
        third = contact_record("Third", "DUP@X.COM")
        other = contact_record("Other", "other@x.com")
        result = run(contacts_source(first, second, third, other))

        self.assertEqual([r.name for r in result.recipients], ["First", "Other"])
        self.assertEqual([r.email for r in result.recipients], ["Dup@X.com", "other@x.com"])
        self.assertEqual(reasons(result), [SkipReason.DUPLICATE_EMAIL] * 2)
        self.assertEqual([s.name for s in result.skipped], ["Second", "Third"])
        self.assertEqual(result.batches, [["dup@x.com", "other@x.com"]])

    def test_duplicates_across_a_lead_and_a_contact_in_the_registry(self):
        registry = EmailRegistry()
        self.assertTrue(registry.claim("A@x.com"))
        self.assertFalse(registry.claim(" a@X.COM "))
        self.assertTrue(registry.claim("b@x.com"))


class IdsModeTests(SimpleTestCase):
    def test_unknown_ids_are_not_found_in_request_order(self):
        known_a = contact_record("A", "a@x.com")
        known_b = contact_record("B", "b@x.com")
        missing_1, missing_2 = uuid4(), uuid4()
        source = contacts_source(known_a, known_b)

        result = run(source, ids=[known_a.record_id, missing_1, known_b.record_id, missing_2])

        self.assertEqual(result.selected, 4)
        self.assertEqual([r.name for r in result.recipients], ["A", "B"])  # request order
        self.assertEqual([s.record_id for s in result.skipped], [missing_1, missing_2])
        for skip in result.skipped:
            self.assertEqual(skip.reason, SkipReason.NOT_FOUND)
            self.assertEqual(skip.record_type, RecordType.CONTACT)
            self.assertEqual(skip.name, "")

    def test_not_found_has_the_record_type_of_the_entity(self):
        for source, expected in (
            (contacts_source(), RecordType.CONTACT),
            (leads_source(), RecordType.LEAD),
            (accounts_source(), RecordType.ACCOUNT),
        ):
            with self.subTest(entity=source.entity):
                result = run(source, ids=[uuid4()])
                self.assertEqual(result.skipped[0].record_type, expected)

    def test_repeated_ids_count_once_and_are_looked_up_once(self):
        record = contact_record()
        source = contacts_source(record)
        result = run(source, ids=[record.record_id, record.record_id])
        self.assertEqual(result.selected, 1)
        self.assertEqual(len(result.recipients), 1)
        self.assertEqual(result.skipped, [])
        self.assertEqual(source.id_calls, [[record.record_id]])

    def test_ids_are_fetched_with_one_call(self):
        records = [contact_record(email=f"p{i}@x.com") for i in range(30)]
        source = contacts_source(*records)
        run(source)
        self.assertEqual(len(source.id_calls), 1)

    def test_ids_cap(self):
        source = contacts_source()
        ok = [uuid4() for _ in range(MAX_IDS)]
        self.assertEqual(run(source, ids=ok).selected, MAX_IDS)

        with self.assertRaisesRegex(ValueError, "at most 500 ids"):
            run(source, ids=[uuid4() for _ in range(MAX_IDS + 1)])

    def test_cap_counts_the_ids_as_sent_even_when_repeated(self):
        one = uuid4()
        with self.assertRaisesRegex(ValueError, "at most 500 ids"):
            run(contacts_source(), ids=[one] * (MAX_IDS + 1))

    def test_empty_ids_are_refused(self):
        with self.assertRaisesRegex(ValueError, "at least one id"):
            run(contacts_source(), ids=[])


class FilterModeTests(SimpleTestCase):
    def filter_selection(self, **kwargs):
        return FilterSelection(**kwargs)

    def test_search_and_filters_are_handed_to_the_source_with_the_cap(self):
        source = contacts_source(contact_record())
        filters = (FilterSpec("department", "equals", "Sales"),)
        run(source, selection=self.filter_selection(search="ann", filters=filters))
        self.assertEqual(source.match_calls, [("ann", filters, MAX_FILTER_MATCHES)])
        self.assertEqual(MAX_FILTER_MATCHES, 2000)

    def test_exclude_ids_are_removed_from_the_selection(self):
        keep = contact_record("Keep", "keep@x.com")
        drop = contact_record("Drop", "drop@x.com")
        source = contacts_source(keep, drop)

        result = run(
            source,
            selection=self.filter_selection(exclude_ids=(drop.record_id, uuid4())),
        )

        self.assertEqual(result.selected, 1)
        self.assertEqual([r.name for r in result.recipients], ["Keep"])
        self.assertEqual(result.skipped, [])  # excluded records are not "skipped"

    def test_filter_mode_keeps_list_order(self):
        records = [contact_record(f"N{i}", f"n{i}@x.com") for i in range(5)]
        result = run(contacts_source(*records), selection=self.filter_selection())
        self.assertEqual([r.name for r in result.recipients], [f"N{i}" for i in range(5)])

    def test_a_record_returned_twice_by_the_source_counts_once(self):
        record = contact_record()
        result = run(contacts_source(record, record), selection=self.filter_selection())
        self.assertEqual(result.selected, 1)
        self.assertEqual(len(result.recipients), 1)
        self.assertEqual(result.skipped, [])

    def test_no_matches_is_an_empty_success(self):
        result = run(contacts_source(), selection=self.filter_selection(search="zzz"))
        self.assertEqual((result.selected, result.recipients, result.skipped, result.batches), (0, [], [], []))

    def test_more_than_the_cap_is_refused(self):
        records = [contact_record(email=f"p{i}@x.com") for i in range(MAX_FILTER_MATCHES + 1)]
        with self.assertRaises(SelectionTooLargeError):
            run(contacts_source(*records), selection=self.filter_selection())

    def test_exactly_the_cap_is_accepted(self):
        records = [contact_record(email=f"p{i}@x.com") for i in range(MAX_FILTER_MATCHES)]
        result = run(contacts_source(*records), selection=self.filter_selection())
        self.assertEqual(result.selected, MAX_FILTER_MATCHES)
        self.assertEqual(len(result.recipients), MAX_FILTER_MATCHES)

    def test_exclude_ids_cap(self):
        with self.assertRaisesRegex(ValueError, "exclude_ids accepts at most 2000"):
            run(
                contacts_source(),
                selection=self.filter_selection(
                    exclude_ids=tuple(uuid4() for _ in range(MAX_EXCLUDE_IDS + 1))
                ),
            )

    def test_source_errors_for_bad_filters_propagate_as_value_error(self):
        class Refusing(FakeSource):
            def get_matching(self, search, filters, max_matches):
                raise ValueError("Filtering is not supported for field 'x'.")

        source = Refusing(MailEntity.CONTACTS, RecordType.CONTACT)
        with self.assertRaisesRegex(ValueError, "not supported for field 'x'"):
            run(source, selection=self.filter_selection())


class BatchingTests(SimpleTestCase):
    def records(self, n):
        return [contact_record(f"C{i}", f"c{i}@x.com") for i in range(n)]

    def sizes(self, n, batch_size=40):
        # Filter mode, so that "no records at all" is a valid selection too.
        result = run(
            contacts_source(*self.records(n)),
            batch_size=batch_size,
            selection=FilterSelection(),
        )
        return [len(batch) for batch in result.batches]

    def test_boundaries_with_the_default_size_of_40(self):
        self.assertEqual(self.sizes(0), [])
        self.assertEqual(self.sizes(1), [1])
        self.assertEqual(self.sizes(40), [40])
        self.assertEqual(self.sizes(41), [40, 1])
        self.assertEqual(self.sizes(80), [40, 40])
        self.assertEqual(self.sizes(81), [40, 40, 1])

    def test_boundaries_with_a_custom_size(self):
        self.assertEqual(self.sizes(0, 7), [])
        self.assertEqual(self.sizes(1, 7), [1])
        self.assertEqual(self.sizes(7, 7), [7])
        self.assertEqual(self.sizes(8, 7), [7, 1])
        self.assertEqual(self.sizes(1, 1), [1])
        self.assertEqual(self.sizes(3, 1), [1, 1, 1])
        self.assertEqual(self.sizes(51, 50), [50, 1])

    def test_batches_hold_only_lower_cased_eligible_addresses_in_order(self):
        records = [
            contact_record("A", "A@X.com"),
            contact_record("B", None),
            contact_record("C", "c@x.com", opt_out=True),
            contact_record("D", "D@x.com"),
            contact_record("E", "a@x.com"),
        ]
        result = run(contacts_source(*records), batch_size=1)
        self.assertEqual(result.batches, [["a@x.com"], ["d@x.com"]])

    def test_batches_match_recipients_in_order(self):
        result = run(contacts_source(*self.records(95)), batch_size=40)
        flat = [address for batch in result.batches for address in batch]
        self.assertEqual(flat, [r.email_key for r in result.recipients])

    def test_batch_size_limits(self):
        source = contacts_source(contact_record())
        for bad in (0, -1, 51, 100, True, "40", 40.5, None):
            with self.subTest(batch_size=bad):
                with self.assertRaisesRegex(ValueError, "batch_size"):
                    run(source, batch_size=bad)
        for good in (1, 40, 50):
            with self.subTest(batch_size=good):
                self.assertEqual(run(source, batch_size=good).batches, [["ann@x.com"]])

    def test_chunk_helper(self):
        self.assertEqual(chunk([], 3), [])
        self.assertEqual(chunk([1, 2, 3], 3), [[1, 2, 3]])
        self.assertEqual(chunk([1, 2, 3, 4], 3), [[1, 2, 3], [4]])
        with self.assertRaises(ValueError):
            chunk([1], 0)
        self.assertEqual(validate_batch_size(50), 50)


class SummaryTests(SimpleTestCase):
    def test_mixed_selection_adds_up(self):
        records = [
            contact_record("Ok1", "ok1@x.com"),
            contact_record("Ok2", "ok2@x.com"),
            contact_record("Out", "out@x.com", opt_out=True),
            contact_record("None", None),
            contact_record("Dup", "OK1@x.com"),
        ]
        ids = [r.record_id for r in records] + [uuid4()]
        result = run(contacts_source(*records), ids=ids)

        self.assertEqual(result.selected, 6)
        self.assertEqual(len(result.recipients), 2)
        self.assertEqual(
            reasons(result),
            [SkipReason.OPTED_OUT, SkipReason.NO_EMAIL, SkipReason.DUPLICATE_EMAIL, SkipReason.NOT_FOUND],
        )
        self.assertEqual(result.batches, [["ok1@x.com", "ok2@x.com"]])

    def test_check_email_helper(self):
        self.assertIsNone(check_email("a@x.com", fake_is_valid))
        self.assertEqual(check_email(None, fake_is_valid), SkipReason.NO_EMAIL)
        self.assertEqual(check_email("  ", fake_is_valid), SkipReason.NO_EMAIL)
        self.assertEqual(check_email("bad", fake_is_valid), SkipReason.INVALID_EMAIL)


class LayerRulesTests(SimpleTestCase):
    """domain/ and application/ never import Django, DRF, ORM or other modules."""

    ALLOWED_PREFIXES = ("src.modules.mailing.domain", "src.modules.mailing.application")
    ALLOWED_STDLIB = {"__future__", "dataclasses", "enum", "typing", "uuid"}

    def test_domain_and_application_are_framework_free(self):
        root = pathlib.Path(__file__).parent
        files = [
            path
            for layer in ("domain", "application")
            for path in (root / layer).rglob("*.py")
        ]
        self.assertTrue(files)

        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:  # relative import inside the same layer
                        continue
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    allowed = name.split(".")[0] in self.ALLOWED_STDLIB or name.startswith(
                        self.ALLOWED_PREFIXES
                    )
                    self.assertTrue(allowed, f"{path.name} imports {name}")
