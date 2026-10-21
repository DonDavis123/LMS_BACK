"""Unit tests (no database) for the one-row-per-record calls list and the
detailed record history."""

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.modules.calls.application.dto.get_call import GetCallDTO
from src.modules.calls.application.dto.get_call_record import GetCallRecordDTO
from src.modules.calls.application.services.call_history import (
    build_record_history,
    format_duration,
)
from src.modules.calls.application.use_cases.get_call_record_history import (
    GetCallRecordHistoryUseCase,
)
from src.modules.calls.application.use_cases.get_call_records import (
    GetCallRecordsUseCase,
)
from src.modules.calls.domain.entities.call import Call
from src.modules.calls.domain.enums.call_entry_method import CallEntryMethod
from src.modules.calls.domain.enums.call_outcome import CallOutcome
from src.modules.calls.domain.enums.call_type import CallType
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


def make_call(*, lead_id=None, contact_id=None, minutes_ago=60, **kw) -> Call:
    now = datetime.now(timezone.utc)
    values = dict(
        id=uuid4(),
        lead_id=lead_id,
        contact_id=contact_id,
        account_id=None,
        owner_id=uuid4(),
        call_type=CallType.OUTBOUND,
        outcome=CallOutcome.CONNECTED,
        call_start_time=now - timedelta(minutes=minutes_ago),
        duration_seconds=250,
        description="Discussed pricing",
        entry_method=CallEntryMethod.MANUAL,
        created_by_id=uuid4(),
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )
    values.update(kw)
    return Call(**values)


def dto(call: Call, lead_name=None, contact_name=None) -> GetCallDTO:
    return GetCallDTO(
        call=call,
        lead_name=lead_name,
        contact_name=contact_name,
        account_name=None,
        owner_name="Asha",
    )


def event(event_type, call_id, minutes_ago, changes=None, **metadata):
    meta = {"call_id": str(call_id), **metadata}
    if changes is not None:
        meta["changes"] = changes
    return {
        "id": uuid4(),
        "event_type": event_type,
        "actor": {"id": uuid4(), "name": "Asha"},
        "message": event_type,
        "metadata": meta,
        "created_at": datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    }


class FormatDurationTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(format_duration(0), "0 sec")
        self.assertEqual(format_duration(250), "4 min 10 sec")
        self.assertEqual(format_duration(3725), "1 hr 2 min 5 sec")
        self.assertIsNone(format_duration(None))


class BuildRecordHistoryTests(unittest.TestCase):
    def live(self, call: Call):
        return {
            "call_start_time": call.call_start_time,
            "duration_seconds": call.duration_seconds,
            "call_type": call.call_type.value,
            "outcome": call.outcome.value,
            "description": call.description,
            "owner_name": "Asha",
        }

    def test_logged_event_shows_the_call_as_it_was_before_edits(self):
        call = make_call(
            lead_id=uuid4(),
            duration_seconds=300,
            description="Customer asked for a revised quote.",
        )
        logged = event("CALL_LOGGED", call.id, 120)
        updated = event(
            "CALL_UPDATED",
            call.id,
            30,
            changes={
                "duration_seconds": {"old_value": 250, "new_value": 300},
                "description": {
                    "old_value": "Discussed pricing",
                    "new_value": "Customer asked for a revised quote.",
                },
            },
        )

        history = build_record_history(
            [updated, logged],  # newest first
            {str(call.id): self.live(call)},
        )

        self.assertEqual([h["event_type"] for h in history], ["CALL_UPDATED", "CALL_LOGGED"])
        # After the edit: the current values.
        self.assertEqual(history[0]["call"]["duration_seconds"], 300)
        self.assertEqual(history[0]["call"]["description"], "Customer asked for a revised quote.")
        # When it was logged: the original values.
        self.assertEqual(history[1]["call"]["duration_seconds"], 250)
        self.assertEqual(history[1]["call"]["duration_label"], "4 min 10 sec")
        self.assertEqual(history[1]["call"]["description"], "Discussed pricing")
        self.assertEqual(history[1]["call"]["call_start_time"], call.call_start_time)
        self.assertEqual(history[1]["call"]["owner_name"], "Asha")
        self.assertEqual(history[1]["call_id"], str(call.id))

    def test_start_time_edit_is_undone_from_iso_string(self):
        call = make_call(lead_id=uuid4(), minutes_ago=10)
        original_start = call.call_start_time - timedelta(hours=1)
        updated = event(
            "CALL_UPDATED",
            call.id,
            5,
            changes={
                "call_start_time": {
                    "old_value": original_start.isoformat(),
                    "new_value": call.call_start_time.isoformat(),
                }
            },
        )
        logged = event("CALL_LOGGED", call.id, 100)

        history = build_record_history([updated, logged], {str(call.id): self.live(call)})

        self.assertEqual(history[1]["call"]["call_start_time"], original_start)

    def test_events_of_several_calls_are_kept_separate(self):
        lead_id = uuid4()
        first = make_call(lead_id=lead_id, description="first", minutes_ago=300)
        second = make_call(lead_id=lead_id, description="second", minutes_ago=50)
        events = [
            event("CALL_LOGGED", second.id, 49),
            event("CALL_LOGGED", first.id, 299),
        ]

        history = build_record_history(
            events,
            {str(first.id): self.live(first), str(second.id): self.live(second)},
        )

        self.assertEqual([h["call"]["description"] for h in history], ["second", "first"])

    def test_deleted_call_is_rebuilt_from_event_metadata(self):
        call_id = uuid4()
        logged = event(
            "CALL_LOGGED", call_id, 100, outcome="Busy", duration_seconds=60, description="Left note"
        )
        deleted = event("CALL_DELETED", call_id, 10, outcome="Busy", duration_seconds=60)

        history = build_record_history([deleted, logged], {})  # not live any more

        self.assertEqual(history[1]["call"]["outcome"], "Busy")
        self.assertEqual(history[1]["call"]["description"], "Left note")
        self.assertEqual(history[0]["call"]["duration_label"], "1 min 0 sec")
        self.assertIsNone(history[0]["call"]["call_start_time"])

    def test_non_call_events_are_ignored(self):
        call = make_call(lead_id=uuid4())
        other = event("LEAD_UPDATED", call.id, 5)

        self.assertEqual(build_record_history([other], {str(call.id): self.live(call)}), [])


class FakeCallRepo:
    def __init__(self, calls=None, summaries=None):
        self.calls = calls or []
        self.summaries = summaries or []

    def get_by_id_with_relations(self, call_id):
        for call in self.calls:
            if call.call.id == call_id:
                return call
        return None

    def get_by_related_record(self, *, lead_id=None, contact_id=None, exclude_call_id=None, limit=50):
        rows = [
            c for c in self.calls
            if (lead_id and c.call.lead_id == lead_id)
            or (contact_id and c.call.contact_id == contact_id)
        ]
        rows.sort(key=lambda c: c.call.call_start_time, reverse=True)
        return rows[:limit]

    def get_record_summaries(self, query):
        return PaginatedResult(self.summaries, query.page, query.page_size, len(self.summaries))


class FakeTimelineRepo:
    def __init__(self, events=None, latest=None):
        self.events = events or []
        self.latest = latest or {}
        self.latest_requests = []

    def get_for_entity(self, entity_type, entity_id):
        return self.events

    def get_latest_for_entities(self, entity_type, entity_ids, event_type_prefix=None):
        self.latest_requests.append((entity_type, list(entity_ids), event_type_prefix))
        return {i: self.latest[i] for i in entity_ids if i in self.latest}


class GetCallRecordsUseCaseTests(unittest.TestCase):
    def test_attaches_latest_update_per_record_and_keeps_one_row_each(self):
        lead_id, contact_id, quiet_lead_id = uuid4(), uuid4(), uuid4()
        lead_call = make_call(lead_id=lead_id)
        contact_call = make_call(contact_id=contact_id)
        quiet_call = make_call(lead_id=quiet_lead_id)
        now = datetime.now(timezone.utc)

        rows = [
            GetCallRecordDTO("LEAD", lead_id, "Priya", 3, now, dto(lead_call, lead_name="Priya")),
            GetCallRecordDTO("CONTACT", contact_id, "Jane", 1, now, dto(contact_call, contact_name="Jane")),
            GetCallRecordDTO("LEAD", quiet_lead_id, "Quiet", 1, now, dto(quiet_call, lead_name="Quiet")),
        ]
        lead_event = {"id": uuid4(), "event_type": "CALL_UPDATED", "metadata": {}}
        contact_event = {"id": uuid4(), "event_type": "CALL_LOGGED", "metadata": {}}
        timeline = FakeTimelineRepo(latest={lead_id: lead_event, contact_id: contact_event})

        result = GetCallRecordsUseCase(FakeCallRepo(summaries=rows), timeline).execute(
            ListQuery(page=1, page_size=10)
        )

        self.assertEqual(result.total, 3)
        self.assertEqual([r.record_id for r in result.results], [lead_id, contact_id, quiet_lead_id])
        self.assertIs(result.results[0].latest_update, lead_event)
        self.assertIs(result.results[1].latest_update, contact_event)
        self.assertIsNone(result.results[2].latest_update)
        self.assertEqual(result.results[0].call_count, 3)
        # One timeline lookup per record type, limited to call events.
        self.assertEqual(
            sorted((t, p) for t, _, p in timeline.latest_requests),
            [("CONTACT", "CALL_"), ("LEAD", "CALL_")],
        )

    def test_empty_page_makes_no_timeline_lookup(self):
        timeline = FakeTimelineRepo()

        result = GetCallRecordsUseCase(FakeCallRepo(), timeline).execute(ListQuery())

        self.assertEqual(result.results, [])
        self.assertEqual(timeline.latest_requests, [])


class GetCallRecordHistoryUseCaseTests(unittest.TestCase):
    def test_history_covers_every_call_of_the_record(self):
        lead_id = uuid4()
        older = make_call(lead_id=lead_id, minutes_ago=300, description="older")
        current = make_call(lead_id=lead_id, minutes_ago=30, description="current")
        other_lead_call = make_call(lead_id=uuid4())
        repo = FakeCallRepo(
            calls=[
                dto(older, lead_name="Priya"),
                dto(current, lead_name="Priya"),
                dto(other_lead_call, lead_name="Other"),
            ]
        )
        timeline = FakeTimelineRepo(
            events=[
                event("CALL_LOGGED", current.id, 29),
                event("CALL_LOGGED", older.id, 299),
            ]
        )

        history = GetCallRecordHistoryUseCase(repo, timeline).execute(current.id)

        self.assertEqual(history.related_record_type, "LEAD")
        self.assertEqual(history.related_record_id, lead_id)
        self.assertEqual(history.related_record_name, "Priya")
        self.assertEqual(history.total_calls_for_record, 2)
        self.assertEqual([e["call"]["description"] for e in history.events], ["current", "older"])
        self.assertEqual(history.events[0]["call"]["outcome"], "Connected")

    def test_contact_call_uses_contact_record(self):
        contact_id = uuid4()
        call = make_call(contact_id=contact_id)
        repo = FakeCallRepo(calls=[dto(call, contact_name="Jane")])

        history = GetCallRecordHistoryUseCase(repo, FakeTimelineRepo()).execute(call.id)

        self.assertEqual(history.related_record_type, "CONTACT")
        self.assertEqual(history.related_record_id, contact_id)
        self.assertEqual(history.events, [])

    def test_unknown_or_deleted_call_returns_none(self):
        gone = make_call(lead_id=uuid4(), is_deleted=True)
        repo = FakeCallRepo(calls=[dto(gone)])
        use_case = GetCallRecordHistoryUseCase(repo, FakeTimelineRepo())

        self.assertIsNone(use_case.execute(uuid4()))
        self.assertIsNone(use_case.execute(gone.id))


if __name__ == "__main__":
    unittest.main()
