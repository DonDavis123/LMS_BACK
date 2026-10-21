import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.modules.calls.domain.entities.call import Call
from src.modules.calls.domain.enums.call_entry_method import CallEntryMethod
from src.modules.calls.domain.enums.call_outcome import CallOutcome
from src.modules.calls.domain.enums.call_type import CallType


class CallEntityTests(unittest.TestCase):

    def setUp(self):
        self.owner_id = uuid4()
        self.lead_id = uuid4()
        self.contact_id = uuid4()
        self.account_id = uuid4()
        self.started = datetime.now(timezone.utc) - timedelta(minutes=10)

    def make(self, **overrides):
        values = dict(
            owner_id=self.owner_id,
            created_by_id=self.owner_id,
            call_start_time=self.started,
            outcome=CallOutcome.CONNECTED,
            lead_id=self.lead_id,
        )
        values.update(overrides)
        return Call.create(**values)

    def test_create_lead_call_with_defaults(self):
        call = self.make()

        self.assertEqual(call.lead_id, self.lead_id)
        self.assertIsNone(call.contact_id)
        self.assertEqual(call.call_type, CallType.OUTBOUND)
        self.assertEqual(call.entry_method, CallEntryMethod.MANUAL)
        self.assertEqual(call.duration_seconds, 0)
        self.assertIsNone(call.description)
        self.assertFalse(call.is_deleted)

    def test_create_contact_call_with_account(self):
        call = self.make(
            lead_id=None,
            contact_id=self.contact_id,
            account_id=self.account_id,
        )

        self.assertEqual(call.contact_id, self.contact_id)
        self.assertEqual(call.account_id, self.account_id)

    def test_requires_exactly_one_of_lead_or_contact(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.make(lead_id=None, contact_id=None)

        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.make(contact_id=self.contact_id)

    def test_account_requires_contact(self):
        with self.assertRaisesRegex(ValueError, "account requires"):
            self.make(account_id=self.account_id)

    def test_duration_bounds(self):
        self.assertEqual(self.make(duration_seconds=0).duration_seconds, 0)
        self.assertEqual(
            self.make(duration_seconds=86400).duration_seconds,
            86400,
        )

        for invalid in (-1, 86401, 1.5, "10", True, None):
            with self.subTest(duration=invalid):
                with self.assertRaisesRegex(ValueError, "duration"):
                    self.make(duration_seconds=invalid)

    def test_description_is_trimmed_and_blank_becomes_none(self):
        self.assertEqual(self.make(description="  hello  ").description, "hello")
        self.assertIsNone(self.make(description="   ").description)
        self.assertIsNone(self.make(description="").description)

    def test_description_max_length(self):
        self.assertEqual(len(self.make(description="x" * 1000).description), 1000)

        with self.assertRaisesRegex(ValueError, "1000"):
            self.make(description="x" * 1001)

    def test_description_length_is_checked_after_trimming(self):
        call = self.make(description=" " + "x" * 1000 + " ")

        self.assertEqual(len(call.description), 1000)

    def test_call_start_time_is_required(self):
        with self.assertRaisesRegex(ValueError, "start time is required"):
            self.make(call_start_time=None)

        with self.assertRaisesRegex(ValueError, "must be a datetime"):
            self.make(call_start_time="2026-01-01")

    def test_call_start_time_future_tolerance(self):
        soon = datetime.now(timezone.utc) + timedelta(minutes=4)
        self.assertEqual(self.make(call_start_time=soon).call_start_time, soon)

        too_late = datetime.now(timezone.utc) + timedelta(minutes=6)
        with self.assertRaisesRegex(ValueError, "future"):
            self.make(call_start_time=too_late)

    def test_naive_start_time_is_treated_as_utc(self):
        naive_past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        self.assertEqual(
            self.make(call_start_time=naive_past).call_start_time,
            naive_past,
        )

        naive_future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        with self.assertRaisesRegex(ValueError, "future"):
            self.make(call_start_time=naive_future)

    def test_owner_and_creator_are_required(self):
        with self.assertRaisesRegex(ValueError, "owner is required"):
            self.make(owner_id=None)

        with self.assertRaisesRegex(ValueError, "creator is required"):
            self.make(created_by_id=None)

    def test_invalid_enum_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "outcome"):
            self.make(outcome="Exploded")

        with self.assertRaisesRegex(ValueError, "type"):
            self.make(call_type="Telepathy")

    def test_string_enum_values_are_coerced(self):
        call = self.make(outcome="Busy", call_type="Inbound")

        self.assertIs(call.outcome, CallOutcome.BUSY)
        self.assertIs(call.call_type, CallType.INBOUND)

    def test_soft_delete(self):
        call = self.make()

        call.soft_delete()

        self.assertTrue(call.is_deleted)
        with self.assertRaisesRegex(ValueError, "already deleted"):
            call.soft_delete()

    def test_duration_label(self):
        cases = {
            0: "0 sec",
            45: "45 sec",
            60: "1 min 0 sec",
            250: "4 min 10 sec",
            3725: "1 hr 2 min 5 sec",
        }
        for seconds, expected in cases.items():
            with self.subTest(seconds=seconds):
                self.assertEqual(
                    self.make(duration_seconds=seconds).duration_label(),
                    expected,
                )

    def test_enum_values(self):
        self.assertEqual(CallType.OUTBOUND.value, "Outbound")
        self.assertEqual(CallOutcome.CALLBACK_REQUESTED.value, "Callback Requested")
        self.assertEqual(CallEntryMethod.TIMER.value, "TIMER")
