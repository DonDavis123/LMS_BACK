import ast
import pathlib
from uuid import uuid4

from django.test import SimpleTestCase

from src.modules.email_activity.application.dto.log_email_compose import (
    MAX_MESSAGE_LENGTH,
    MAX_SUBJECT_LENGTH,
    MAX_TARGETS,
    ComposeTarget,
    LogEmailComposeCommand,
)
from src.modules.email_activity.application.interfaces.compose_log import ComposeLog
from src.modules.email_activity.application.interfaces.record_lookup import (
    RecordLookup,
)
from src.modules.email_activity.application.use_cases.log_email_compose import (
    LogEmailComposeUseCase,
    normalize_subject,
)
from src.modules.email_activity.domain.enums.channel import EmailChannel
from src.modules.email_activity.domain.enums.record_type import RecordType


class FakeLookup(RecordLookup):
    """``{id: email}`` of the records that exist for the caller."""

    def __init__(self, emails=None):
        self.emails = dict(emails or {})
        self.calls = []

    def find_emails(self, ids):
        self.calls.append(list(ids))
        return {i: self.emails[i] for i in ids if i in self.emails}


class FakeComposeLog(ComposeLog):
    def __init__(self):
        self.events = []
        self.find_calls = 0
        self.fail_on_record = False

    def find_logged(self, targets, client_ref):
        self.find_calls += 1
        return {
            e.target
            for e in self.events
            if e.target in targets and e.metadata["client_ref"] == client_ref
        }

    def record(self, events):
        if self.fail_on_record:
            raise RuntimeError("database down")
        self.events.extend(events)


class RecordingTransaction:
    def __init__(self):
        self.executions = 0

    def execute(self, operation):
        self.executions += 1
        return operation()


class LogEmailComposeBase(SimpleTestCase):
    def setUp(self):
        self.actor_id = uuid4()
        self.contact_a = uuid4()
        self.contact_b = uuid4()
        self.lead_a = uuid4()
        self.contacts = FakeLookup(
            {self.contact_a: "ann@example.com", self.contact_b: None}
        )
        self.leads = FakeLookup({self.lead_a: "  lee@example.com "})
        self.log = FakeComposeLog()
        self.transaction = RecordingTransaction()
        self.use_case = LogEmailComposeUseCase(
            {RecordType.CONTACT: self.contacts, RecordType.LEAD: self.leads},
            self.log,
            self.transaction,
        )

    def command(self, targets, **overrides):
        values = dict(
            actor_id=self.actor_id,
            actor_name="Don Davis",
            client_ref=uuid4(),
            channel=EmailChannel.GMAIL_COMPOSE,
            targets=tuple(targets),
        )
        values.update(overrides)
        return LogEmailComposeCommand(**values)

    @staticmethod
    def contact(record_id):
        return ComposeTarget(RecordType.CONTACT, record_id)

    @staticmethod
    def lead(record_id):
        return ComposeTarget(RecordType.LEAD, record_id)


class EventPerTargetTests(LogEmailComposeBase):
    def test_writes_one_event_per_target_with_message_and_metadata(self):
        ref = uuid4()
        result = self.use_case.execute(
            self.command(
                [self.contact(self.contact_a), self.lead(self.lead_a)],
                client_ref=ref,
                subject="  Hello  ",
                batch_index=2,
                batch_total=3,
            )
        )

        self.assertEqual((result.logged, result.already_logged), (2, 0))
        self.assertEqual(result.not_found, ())
        self.assertEqual(len(self.log.events), 2)

        by_target = {event.target: event for event in self.log.events}
        contact_event = by_target[self.contact(self.contact_a)]
        self.assertEqual(contact_event.actor_id, self.actor_id)
        self.assertEqual(contact_event.message, "Email opened in Gmail by Don Davis")
        self.assertEqual(
            contact_event.metadata,
            {
                "client_ref": str(ref),
                "channel": "GMAIL_COMPOSE",
                "subject": "Hello",
                "recipient_email": "ann@example.com",
                "batch_index": 2,
                "batch_total": 3,
            },
        )
        # Each record's own email, trimmed.
        self.assertEqual(
            by_target[self.lead(self.lead_a)].metadata["recipient_email"],
            "lee@example.com",
        )

    def test_a_record_without_email_gets_a_null_recipient_email(self):
        self.use_case.execute(self.command([self.contact(self.contact_b)]))

        self.assertIsNone(self.log.events[0].metadata["recipient_email"])

    def test_optional_fields_are_null_when_missing(self):
        self.use_case.execute(self.command([self.contact(self.contact_a)]))

        metadata = self.log.events[0].metadata
        self.assertIsNone(metadata["subject"])
        self.assertIsNone(metadata["batch_index"])
        self.assertIsNone(metadata["batch_total"])

    def test_wording_never_claims_the_email_was_sent(self):
        self.use_case.execute(self.command([self.contact(self.contact_a)]))

        message = self.log.events[0].message.lower()
        self.assertIn("opened", message)
        self.assertNotIn("sent", message)

    def test_no_event_exposes_the_other_recipients(self):
        self.use_case.execute(
            self.command([self.contact(self.contact_a), self.lead(self.lead_a)])
        )

        for event in self.log.events:
            text = repr(event)
            others = {"ann@example.com", "lee@example.com"} - {
                event.metadata["recipient_email"]
            }
            for other in others:
                self.assertNotIn(other, text)

    def test_a_long_actor_name_is_cut_to_the_message_limit(self):
        self.use_case.execute(
            self.command([self.contact(self.contact_a)], actor_name="N" * 900)
        )

        self.assertEqual(len(self.log.events[0].message), MAX_MESSAGE_LENGTH)

    def test_records_are_written_in_one_transaction(self):
        self.use_case.execute(
            self.command([self.contact(self.contact_a), self.lead(self.lead_a)])
        )

        self.assertEqual(self.transaction.executions, 1)

    def test_a_failing_write_propagates_so_the_transaction_rolls_back(self):
        self.log.fail_on_record = True

        with self.assertRaises(RuntimeError):
            self.use_case.execute(self.command([self.contact(self.contact_a)]))

    def test_each_record_type_is_looked_up_once_for_all_its_targets(self):
        self.use_case.execute(
            self.command(
                [
                    self.contact(self.contact_a),
                    self.contact(self.contact_b),
                    self.lead(self.lead_a),
                ]
            )
        )

        self.assertEqual(len(self.contacts.calls), 1)
        self.assertEqual(len(self.leads.calls), 1)
        self.assertEqual(self.log.find_calls, 1)


class IdempotencyTests(LogEmailComposeBase):
    def test_same_client_ref_never_creates_a_second_event(self):
        command = self.command(
            [self.contact(self.contact_a), self.lead(self.lead_a)]
        )

        first = self.use_case.execute(command)
        second = self.use_case.execute(command)

        self.assertEqual((first.logged, first.already_logged), (2, 0))
        self.assertEqual((second.logged, second.already_logged), (0, 2))
        self.assertEqual(len(self.log.events), 2)

    def test_a_retry_with_one_more_target_only_writes_the_new_one(self):
        ref = uuid4()
        self.use_case.execute(
            self.command([self.contact(self.contact_a)], client_ref=ref)
        )

        result = self.use_case.execute(
            self.command(
                [self.contact(self.contact_a), self.lead(self.lead_a)],
                client_ref=ref,
            )
        )

        self.assertEqual((result.logged, result.already_logged), (1, 1))
        self.assertEqual(len(self.log.events), 2)

    def test_a_new_client_ref_is_a_new_compose_action(self):
        targets = [self.contact(self.contact_a)]

        self.use_case.execute(self.command(targets))
        result = self.use_case.execute(self.command(targets))

        self.assertEqual(result.logged, 1)
        self.assertEqual(len(self.log.events), 2)

    def test_the_same_id_as_lead_and_as_contact_are_different_targets(self):
        shared = uuid4()
        self.contacts.emails[shared] = "c@example.com"
        self.leads.emails[shared] = "l@example.com"

        result = self.use_case.execute(
            self.command([self.contact(shared), self.lead(shared)])
        )

        self.assertEqual(result.logged, 2)


class NotFoundTests(LogEmailComposeBase):
    def test_unknown_records_are_reported_and_the_rest_is_logged(self):
        missing_contact, missing_lead = uuid4(), uuid4()

        result = self.use_case.execute(
            self.command(
                [
                    self.contact(missing_contact),
                    self.contact(self.contact_a),
                    self.lead(missing_lead),
                ]
            )
        )

        self.assertEqual(result.logged, 1)
        self.assertEqual(
            result.not_found,
            (self.contact(missing_contact), self.lead(missing_lead)),
        )
        self.assertEqual([e.target for e in self.log.events], [self.contact(self.contact_a)])

    def test_nothing_found_writes_nothing_and_opens_no_transaction(self):
        result = self.use_case.execute(self.command([self.contact(uuid4())]))

        self.assertEqual((result.logged, result.already_logged), (0, 0))
        self.assertEqual(len(result.not_found), 1)
        self.assertEqual(self.log.events, [])
        self.assertEqual(self.transaction.executions, 0)

    def test_a_contact_id_given_as_lead_is_not_found(self):
        result = self.use_case.execute(self.command([self.lead(self.contact_a)]))

        self.assertEqual(result.logged, 0)
        self.assertEqual(result.not_found, (self.lead(self.contact_a),))

    def test_a_record_type_without_a_lookup_is_refused(self):
        use_case = LogEmailComposeUseCase(
            {RecordType.CONTACT: self.contacts}, self.log, self.transaction
        )

        with self.assertRaisesMessage(ValueError, "record_type is not supported."):
            use_case.execute(self.command([self.lead(self.lead_a)]))


class CollapseDuplicatesTests(LogEmailComposeBase):
    def test_duplicate_targets_are_collapsed_to_one_event(self):
        target = self.contact(self.contact_a)

        result = self.use_case.execute(self.command([target, target, target]))

        self.assertEqual(result.logged, 1)
        self.assertEqual(len(self.log.events), 1)
        self.assertEqual(self.contacts.calls, [[self.contact_a]])

    def test_a_duplicate_missing_target_is_reported_once(self):
        missing = self.contact(uuid4())

        result = self.use_case.execute(self.command([missing, missing]))

        self.assertEqual(result.not_found, (missing,))

    def test_the_limit_counts_the_targets_as_sent(self):
        target = self.contact(self.contact_a)

        with self.assertRaises(ValueError):
            self.use_case.execute(self.command([target] * (MAX_TARGETS + 1)))


class ValidationTests(LogEmailComposeBase):
    def test_at_least_one_target(self):
        with self.assertRaisesMessage(
            ValueError, "targets must contain at least one target."
        ):
            self.use_case.execute(self.command([]))

    def test_at_most_fifty_targets(self):
        self.contacts.emails.update({uuid4(): None for _ in range(MAX_TARGETS)})
        ids = list(self.contacts.emails)[:MAX_TARGETS]

        result = self.use_case.execute(self.command([self.contact(i) for i in ids]))
        self.assertEqual(result.logged, MAX_TARGETS)

        with self.assertRaisesMessage(
            ValueError, "targets cannot contain more than 50 entries."
        ):
            self.use_case.execute(
                self.command([self.contact(uuid4()) for _ in range(MAX_TARGETS + 1)])
            )

    def test_a_refused_request_writes_nothing(self):
        with self.assertRaises(ValueError):
            self.use_case.execute(
                self.command([self.contact(self.contact_a)], batch_index=5, batch_total=2)
            )

        self.assertEqual(self.log.events, [])
        self.assertEqual(self.contacts.calls, [])

    def test_batch_index_cannot_exceed_batch_total(self):
        with self.assertRaisesMessage(
            ValueError, "batch_index cannot be greater than batch_total."
        ):
            self.use_case.execute(
                self.command([self.contact(self.contact_a)], batch_index=4, batch_total=3)
            )

    def test_batch_index_equal_to_total_is_fine(self):
        result = self.use_case.execute(
            self.command([self.contact(self.contact_a)], batch_index=3, batch_total=3)
        )

        self.assertEqual(result.logged, 1)

    def test_batch_numbers_must_be_positive_whole_numbers(self):
        for field in ("batch_index", "batch_total"):
            for bad in (0, -1, True, 1.5, "2"):
                with self.subTest(field=field, value=bad):
                    with self.assertRaisesMessage(
                        ValueError, f"{field} must be a positive whole number."
                    ):
                        self.use_case.execute(
                            self.command([self.contact(self.contact_a)], **{field: bad})
                        )

    def test_each_batch_number_is_optional_on_its_own(self):
        for overrides in ({"batch_index": 2}, {"batch_total": 4}):
            with self.subTest(overrides=overrides):
                result = self.use_case.execute(
                    self.command([self.contact(self.contact_a)], **overrides)
                )
                self.assertEqual(result.logged, 1)

    def test_only_known_channels_are_accepted(self):
        with self.assertRaisesMessage(ValueError, "channel is not supported."):
            self.use_case.execute(
                self.command([self.contact(self.contact_a)], channel="SMTP")
            )


class SubjectTests(LogEmailComposeBase):
    def test_subject_is_trimmed(self):
        self.assertEqual(normalize_subject("   Hi there \n"), "Hi there")

    def test_blank_or_missing_subject_becomes_none(self):
        self.assertIsNone(normalize_subject(None))
        self.assertIsNone(normalize_subject(""))
        self.assertIsNone(normalize_subject("  \t\n "))

    def test_long_subject_is_truncated_not_rejected(self):
        result = normalize_subject("a" * 500)

        self.assertEqual(len(result), MAX_SUBJECT_LENGTH)

    def test_a_subject_of_exactly_the_limit_is_kept(self):
        self.assertEqual(normalize_subject("b" * MAX_SUBJECT_LENGTH), "b" * MAX_SUBJECT_LENGTH)

    def test_truncation_does_not_leave_trailing_space_or_joiner(self):
        spaced = "a" * (MAX_SUBJECT_LENGTH - 1) + " " + "b" * 20
        joined = "a" * (MAX_SUBJECT_LENGTH - 1) + "\u200d" + "b" * 20

        self.assertEqual(normalize_subject(spaced), "a" * (MAX_SUBJECT_LENGTH - 1))
        self.assertEqual(normalize_subject(joined), "a" * (MAX_SUBJECT_LENGTH - 1))

    def test_astral_characters_are_never_split(self):
        result = normalize_subject("😀" * 300)

        self.assertEqual(result, "😀" * MAX_SUBJECT_LENGTH)
        result.encode("utf-8")  # no lone surrogate

    def test_control_characters_are_replaced_so_the_json_column_accepts_it(self):
        self.assertEqual(normalize_subject("Re:\x00Offer\x07now"), "Re: Offer now")

    def test_the_stored_subject_is_the_normalised_one(self):
        self.use_case.execute(
            self.command([self.contact(self.contact_a)], subject="  " + "s" * 400)
        )

        self.assertEqual(self.log.events[0].metadata["subject"], "s" * MAX_SUBJECT_LENGTH)


class LayerRulesTests(SimpleTestCase):
    """domain/ and application/ never import Django, DRF, ORM or other modules."""

    ALLOWED_PREFIXES = (
        "src.modules.email_activity.domain",
        "src.modules.email_activity.application",
    )
    ALLOWED_STDLIB = {"__future__", "dataclasses", "enum", "typing", "unicodedata", "uuid", "abc"}

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
                    if node.level:
                        continue
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    allowed = name.split(".")[0] in self.ALLOWED_STDLIB or name.startswith(
                        self.ALLOWED_PREFIXES
                    )
                    self.assertTrue(allowed, f"{path.name} imports {name}")

    def test_infrastructure_does_not_import_other_modules(self):
        root = pathlib.Path(__file__).parent / "infrastructure"
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("src.modules."):
                        self.assertTrue(
                            node.module.startswith("src.modules.email_activity"),
                            f"{path.name} imports {node.module}",
                        )
