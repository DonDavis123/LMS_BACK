from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import SimpleTestCase

from src.modules.calls.application.use_cases.mark_missed_calls import MarkMissedCallsUseCase
from src.modules.calls.domain.entities.call import Call
from src.modules.calls.domain.enums.call_outcome import CallOutcome
from src.modules.calls.domain.enums.call_status import CallStatus

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


class _CallRepository:
    def __init__(self, calls):
        self.calls = {call.id: call for call in calls}

    def get_overdue_planned(self, *, started_before, limit=500):
        return sorted(
            (
                c for c in self.calls.values()
                if c.status == CallStatus.PLANNED
                and not c.is_deleted
                and c.call_start_time <= started_before
            ),
            key=lambda c: c.call_start_time,
        )[:limit]

    def get_by_id(self, call_id):
        call = self.calls.get(call_id)
        return replace(call) if call else None

    def save(self, call):
        self.calls[call.id] = call
        return call


class _TimelineRecorder:
    def __init__(self):
        self.events = []

    def record(self, **kwargs):
        self.events.append(kwargs)


class _TransactionManager:
    def execute(self, operation):
        return operation()


def _call(start, status=CallStatus.PLANNED, lead=True):
    return Call.create(
        owner_id=uuid4(),
        created_by_id=uuid4(),
        call_start_time=start,
        outcome=CallOutcome.CONNECTED if status == CallStatus.COMPLETED else None,
        lead_id=uuid4() if lead else None,
        contact_id=None if lead else uuid4(),
        status=status,
    )


class MarkMissedCallsTests(SimpleTestCase):
    def _use_case(self, calls):
        self.repository = _CallRepository(calls)
        self.recorder = _TimelineRecorder()
        return MarkMissedCallsUseCase(self.repository, self.recorder, _TransactionManager())

    def test_entity_only_planned_call_can_be_missed(self):
        call = _call(NOW - timedelta(days=1))
        call.mark_missed()
        self.assertEqual(call.status, CallStatus.MISSED)
        self.assertIsNone(call.outcome)

        with self.assertRaises(ValueError):
            call.mark_missed()

    def test_overdue_planned_call_is_marked_missed_and_recorded(self):
        call = _call(NOW - timedelta(hours=3))
        result = self._use_case([call]).execute(NOW)

        self.assertEqual(result.marked, 1)
        self.assertEqual(self.repository.calls[call.id].status, CallStatus.MISSED)
        self.assertEqual(len(self.recorder.events), 1)
        event = self.recorder.events[0]
        self.assertEqual(event["event_type"], "CALL_UPDATED")
        self.assertEqual(event["actor_id"], call.owner_id)
        self.assertEqual(
            event["metadata"]["changes"]["status"],
            {"old_value": "Planned", "new_value": "Missed"},
        )
        self.assertIn(("CALL", call.id), event["targets"])
        self.assertIn(("LEAD", call.lead_id), event["targets"])

    def test_contact_call_timeline_targets_the_contact(self):
        call = _call(NOW - timedelta(hours=3), lead=False)
        self._use_case([call]).execute(NOW)
        self.assertIn(("CONTACT", call.contact_id), self.recorder.events[0]["targets"])

    def test_call_inside_grace_period_is_left_planned(self):
        call = _call(NOW - timedelta(minutes=30))
        result = self._use_case([call]).execute(NOW)

        self.assertEqual(result.marked, 0)
        self.assertEqual(self.repository.calls[call.id].status, CallStatus.PLANNED)
        self.assertEqual(self.recorder.events, [])

    def test_future_completed_and_missed_calls_are_untouched(self):
        calls = [
            _call(NOW + timedelta(days=1)),
            _call(NOW - timedelta(days=1), status=CallStatus.COMPLETED),
            _call(NOW - timedelta(days=1), status=CallStatus.MISSED),
        ]
        result = self._use_case(calls).execute(NOW)

        self.assertEqual(result.marked, 0)
        self.assertEqual(self.recorder.events, [])

    def test_is_idempotent(self):
        use_case = self._use_case([_call(NOW - timedelta(days=2))])

        self.assertEqual(use_case.execute(NOW).marked, 1)
        self.assertEqual(use_case.execute(NOW).marked, 0)
        self.assertEqual(len(self.recorder.events), 1)

    def test_call_logged_after_the_list_was_loaded_is_not_overwritten(self):
        call = _call(NOW - timedelta(days=1))
        use_case = self._use_case([call])
        stale = list(self.repository.get_overdue_planned(started_before=NOW))
        # The owner logs the call just before the job reaches it.
        self.repository.calls[call.id] = replace(
            call, status=CallStatus.COMPLETED, outcome=CallOutcome.CONNECTED
        )
        self.repository.get_overdue_planned = lambda **_: stale

        result = use_case.execute(NOW)

        self.assertEqual(result.marked, 0)
        self.assertEqual(self.repository.calls[call.id].status, CallStatus.COMPLETED)

    def test_naive_time_is_rejected(self):
        with self.assertRaises(ValueError):
            self._use_case([]).execute(datetime(2026, 11, 10, 12, 0))
