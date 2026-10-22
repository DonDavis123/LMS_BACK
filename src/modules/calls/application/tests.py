import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.modules.calls.application.dto.create_call import CreateCallDTO
from src.modules.calls.application.dto.get_call import GetCallDTO
from src.modules.calls.application.dto.update_call import UpdateCallDTO
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.calls.application.use_cases.create_call import CreateCallUseCase
from src.modules.calls.application.use_cases.delete_call import DeleteCallUseCase
from src.modules.calls.application.use_cases.get_call import GetCallDetailUseCase
from src.modules.calls.application.use_cases.get_calls import GetCallsUseCase
from src.modules.calls.application.use_cases.update_call import UpdateCallUseCase
from src.modules.calls.domain.entities.call import Call
from src.modules.calls.domain.enums.call_entry_method import CallEntryMethod
from src.modules.calls.domain.enums.call_outcome import CallOutcome
from src.modules.calls.domain.enums.call_type import CallType
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User


class FakeTransaction:
    def execute(self, operation):
        return operation()


class FakeTimelineRecorder:
    def __init__(self):
        self.events = []

    def record(
        self,
        event_type,
        actor_id,
        message,
        metadata,
        targets,
    ):
        self.events.append(
            {
                "event_type": event_type,
                "actor_id": actor_id,
                "message": message,
                "metadata": metadata,
                "targets": targets,
            }
        )


class FakeTimelineRepo:
    def __init__(self):
        self.history = {}
        self.requested = []

    def get_for_entity(self, entity_type, entity_id):
        self.requested.append((entity_type, entity_id))
        return self.history.get((entity_type, entity_id), [])


class FakeUserRepo:
    def __init__(self, users):
        self.users = users

    def get_by_id(self, user_id):
        return self.users.get(user_id)


class FakeLead:
    def __init__(self, id, name="Lead", is_deleted=False):
        self.id = id
        self.name = name
        self.is_deleted = is_deleted


class FakeContact:
    def __init__(self, id, name="Contact", is_deleted=False):
        self.id = id
        self.name = name
        self.is_deleted = is_deleted


class FakeAccount:
    def __init__(self, id, account_name="Account", is_deleted=False):
        self.id = id
        self.account_name = account_name
        self.is_deleted = is_deleted


class FakeLeadRepo:
    def __init__(self, leads):
        self.leads = leads

    def get_by_id(self, lead_id):
        return self.leads.get(lead_id)


class FakeContactRepo:
    def __init__(self, contacts):
        self.contacts = contacts

    def get_by_id(self, contact_id):
        return self.contacts.get(contact_id)


class FakeAccountRepo:
    def __init__(self, accounts):
        self.accounts = accounts

    def get_by_id(self, account_id):
        return self.accounts.get(account_id)


class FakeCallRepo(CallRepository):
    """In-memory repository mimicking DjangoCallRepository semantics.

    Like the real one it never returns deleted calls from read methods.
    """

    def __init__(self, lead_names=None, contact_names=None):
        self.calls = {}
        self.save_count = 0
        self.lead_names = lead_names or {}
        self.contact_names = contact_names or {}

    def _dto(self, call):
        return GetCallDTO(
            call=call,
            lead_name=self.lead_names.get(call.lead_id),
            contact_name=self.contact_names.get(call.contact_id),
            account_name=None,
            owner_name="Owner",
        )

    def _active(self):
        return [c for c in self.calls.values() if not c.is_deleted]

    def save(self, call):
        self.save_count += 1
        self.calls[call.id] = call
        return call

    def get_by_id(self, call_id):
        call = self.calls.get(call_id)
        return call if call and not call.is_deleted else None

    def get_by_id_with_relations(self, call_id):
        call = self.get_by_id(call_id)
        return self._dto(call) if call else None

    def get_all_with_relations(self, query):
        active = sorted(
            self._active(),
            key=lambda c: c.call_start_time,
            reverse=True,
        )
        return PaginatedResult(
            [self._dto(c) for c in active],
            query.page,
            query.page_size,
            len(active),
        )

    def _for_record(self, lead_id, contact_id):
        return [
            c for c in self._active()
            if (lead_id is not None and c.lead_id == lead_id)
            or (contact_id is not None and c.contact_id == contact_id)
        ]

    def get_by_related_record(
        self,
        *,
        lead_id=None,
        contact_id=None,
        exclude_call_id=None,
        limit=50,
    ):
        calls = [
            c for c in self._for_record(lead_id, contact_id)
            if c.id != exclude_call_id
        ]
        calls.sort(key=lambda c: c.call_start_time, reverse=True)
        return [self._dto(c) for c in calls[:limit]]

    def count_by_related_record(self, *, lead_id=None, contact_id=None):
        return len(self._for_record(lead_id, contact_id))

    def soft_delete_by_lead_id(self, lead_id):
        return self._soft_delete(lambda c: c.lead_id == lead_id)

    def soft_delete_by_contact_id(self, contact_id):
        return self._soft_delete(lambda c: c.contact_id == contact_id)

    def soft_delete_by_account_id(self, account_id):
        return self._soft_delete(
            lambda c: c.account_id == account_id
            and c.contact_id is None
            and c.lead_id is None
        )

    def _soft_delete(self, predicate):
        ids = [c.id for c in self._active() if predicate(c)]
        for call_id in ids:
            self.calls[call_id].is_deleted = True
        return ids

    def unlink_account_from_contact_calls(self, account_id):
        for call in self._active():
            if call.account_id == account_id and call.contact_id is not None:
                call.account_id = None

    def delete_by_owner_id(self, owner_id):
        ids = [c.id for c in self.calls.values() if c.owner_id == owner_id]
        for call_id in ids:
            del self.calls[call_id]
        return len(ids)

    def count_by_owner_id(self, owner_id):
        return sum(1 for c in self.calls.values() if c.owner_id == owner_id)


def make_user(role=UserRole.ADMIN, is_active=True):
    now = datetime.now(timezone.utc)

    return User(
        uuid4(),
        "User",
        f"{uuid4()}@example.com",
        role,
        is_active,
        now,
        now,
    )


def started(minutes_ago=30):
    return datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)


class CallApplicationTests(unittest.TestCase):

    def setUp(self):
        self.user = make_user()
        self.lead = FakeLead(uuid4(), "Acme Lead")
        self.contact = FakeContact(uuid4(), "Jane Contact")
        self.account = FakeAccount(uuid4())

        self.users = {self.user.id: self.user}
        self.leads = {self.lead.id: self.lead}
        self.contacts = {self.contact.id: self.contact}
        self.accounts = {self.account.id: self.account}

        self.repo = FakeCallRepo(
            lead_names={self.lead.id: self.lead.name},
            contact_names={self.contact.id: self.contact.name},
        )
        self.tx = FakeTransaction()
        self.timeline = FakeTimelineRecorder()
        self.timeline_repo = FakeTimelineRepo()

        self.create_use_case = CreateCallUseCase(
            self.repo,
            FakeUserRepo(self.users),
            FakeLeadRepo(self.leads),
            FakeContactRepo(self.contacts),
            FakeAccountRepo(self.accounts),
            self.timeline,
            self.tx,
        )
        self.update_use_case = UpdateCallUseCase(
            self.repo,
            self.timeline,
            self.tx,
        )
        self.delete_use_case = DeleteCallUseCase(
            self.repo,
            self.timeline,
            self.tx,
        )
        self.detail_use_case = GetCallDetailUseCase(
            self.repo,
            self.timeline_repo,
        )

    def dto(self, **kw):
        values = dict(
            created_by_id=self.user.id,
            call_start_time=started(),
            outcome=CallOutcome.CONNECTED,
            lead_id=self.lead.id,
            duration_seconds=250,
        )
        values.update(kw)
        return CreateCallDTO(**values)

    def log_lead_call(self, **kw):
        return self.create_use_case.execute(self.dto(**kw))

    def log_contact_call(self, **kw):
        values = dict(lead_id=None, contact_id=self.contact.id)
        values.update(kw)
        return self.create_use_case.execute(self.dto(**values))

    # -- create -------------------------------------------------------------

    def test_create_lead_call_records_timeline(self):
        call = self.log_lead_call(description="  asked for a quote  ")

        self.assertEqual(self.repo.calls[call.id], call)
        self.assertEqual(call.owner_id, self.user.id)  # defaults to creator
        self.assertEqual(call.description, "asked for a quote")

        self.assertEqual(len(self.timeline.events), 1)
        event = self.timeline.events[0]
        self.assertEqual(event["event_type"], "CALL_LOGGED")
        self.assertEqual(event["actor_id"], self.user.id)
        self.assertEqual(event["message"], "Call logged (Connected, 4 min 10 sec).")
        self.assertEqual(
            event["metadata"],
            {
                "call_id": str(call.id),
                "outcome": "Connected",
                "duration_seconds": 250,
                "description": "asked for a quote",
            },
        )
        self.assertEqual(
            event["targets"],
            [("CALL", call.id), ("LEAD", self.lead.id)],
        )

    def test_create_contact_call_with_account_targets(self):
        call = self.log_contact_call(account_id=self.account.id)

        self.assertEqual(
            self.timeline.events[0]["targets"],
            [
                ("CALL", call.id),
                ("CONTACT", self.contact.id),
                ("ACCOUNT", self.account.id),
            ],
        )

    def test_each_call_is_a_new_record(self):
        first = self.log_lead_call()
        second = self.log_lead_call()

        self.assertNotEqual(first.id, second.id)
        self.assertEqual(len(self.repo.calls), 2)

    def test_create_uses_explicit_owner(self):
        other = make_user(UserRole.SUPERADMIN)
        self.users[other.id] = other

        call = self.log_lead_call(owner_id=other.id)

        self.assertEqual(call.owner_id, other.id)
        self.assertEqual(call.created_by_id, self.user.id)

    def test_create_rejects_invalid_owner(self):
        inactive = make_user(is_active=False)
        wrong_role = make_user(UserRole.SALES_EXECUTIVE)
        self.users[inactive.id] = inactive
        self.users[wrong_role.id] = wrong_role

        with self.assertRaisesRegex(ValueError, "owner does not exist"):
            self.log_lead_call(owner_id=uuid4())

        with self.assertRaisesRegex(ValueError, "owner is inactive"):
            self.log_lead_call(owner_id=inactive.id)

        with self.assertRaisesRegex(ValueError, "ADMIN or SUPERADMIN"):
            self.log_lead_call(owner_id=wrong_role.id)

        self.assertEqual(self.repo.calls, {})

    def test_create_rejects_missing_or_inactive_creator(self):
        with self.assertRaisesRegex(ValueError, "creator does not exist"):
            self.create_use_case.execute(
                self.dto(created_by_id=uuid4(), owner_id=self.user.id)
            )

        self.user.is_active = False
        with self.assertRaisesRegex(ValueError, "owner is inactive"):
            self.log_lead_call()

    def test_create_rejects_unknown_or_deleted_records(self):
        self.leads[self.lead.id].is_deleted = True
        with self.assertRaisesRegex(ValueError, "lead not found"):
            self.log_lead_call()

        with self.assertRaisesRegex(ValueError, "lead not found"):
            self.log_lead_call(lead_id=uuid4())

        with self.assertRaisesRegex(ValueError, "contact not found"):
            self.log_contact_call(contact_id=uuid4())

        self.contacts[self.contact.id].is_deleted = True
        with self.assertRaisesRegex(ValueError, "contact not found"):
            self.log_contact_call()

        self.accounts[self.account.id].is_deleted = True
        self.contacts[self.contact.id].is_deleted = False
        with self.assertRaisesRegex(ValueError, "account not found"):
            self.log_contact_call(account_id=self.account.id)

        self.assertEqual(self.timeline.events, [])

    def test_create_enforces_entity_rules(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.log_lead_call(lead_id=None)

        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.log_lead_call(contact_id=self.contact.id)

        with self.assertRaisesRegex(ValueError, "account requires"):
            self.log_lead_call(account_id=self.account.id)

        with self.assertRaisesRegex(ValueError, "future"):
            self.log_lead_call(
                call_start_time=datetime.now(timezone.utc) + timedelta(hours=1)
            )

        with self.assertRaisesRegex(ValueError, "duration"):
            self.log_lead_call(duration_seconds=-5)

        self.assertEqual(self.repo.calls, {})
        self.assertEqual(self.timeline.events, [])

    # -- update -------------------------------------------------------------

    def test_update_records_old_and_new_values(self):
        call = self.log_lead_call(description="first note")
        self.timeline.events.clear()

        updated = self.update_use_case.execute(
            UpdateCallDTO(
                call.id,
                {
                    "outcome": CallOutcome.BUSY,
                    "duration_seconds": 30,
                    "description": "  second note ",
                },
            ),
            current_user_id=self.user.id,
        )

        self.assertEqual(updated.outcome, CallOutcome.BUSY)
        self.assertEqual(updated.description, "second note")

        self.assertEqual(len(self.timeline.events), 1)
        event = self.timeline.events[0]
        self.assertEqual(event["event_type"], "CALL_UPDATED")
        self.assertEqual(event["actor_id"], self.user.id)
        self.assertEqual(event["metadata"]["call_id"], str(call.id))
        self.assertEqual(
            event["metadata"]["changes"],
            {
                "outcome": {"old_value": "Connected", "new_value": "Busy"},
                "duration_seconds": {"old_value": 250, "new_value": 30},
                "description": {
                    "old_value": "first note",
                    "new_value": "second note",
                },
            },
        )
        self.assertIn("Outcome: Connected → Busy", event["message"])
        self.assertEqual(
            event["targets"],
            [("CALL", call.id), ("LEAD", self.lead.id)],
        )

    def test_update_without_actual_change_records_nothing(self):
        call = self.log_lead_call(description="note")
        self.timeline.events.clear()

        self.update_use_case.execute(
            UpdateCallDTO(
                call.id,
                {
                    "outcome": "Connected",  # string coerced, same value
                    "duration_seconds": 250,
                    "description": " note ",
                },
            )
        )

        self.assertEqual(self.timeline.events, [])

    def test_update_clearing_description_is_a_change(self):
        call = self.log_lead_call(description="note")
        self.timeline.events.clear()

        updated = self.update_use_case.execute(
            UpdateCallDTO(call.id, {"description": "  "})
        )

        self.assertIsNone(updated.description)
        self.assertEqual(
            self.timeline.events[0]["metadata"]["changes"],
            {"description": {"old_value": "note", "new_value": None}},
        )

    def test_update_rejects_immutable_fields(self):
        call = self.log_lead_call()

        for field, value in (
            ("lead_id", uuid4()),
            ("contact_id", self.contact.id),
            ("account_id", self.account.id),
            ("created_by_id", uuid4()),
            ("entry_method", CallEntryMethod.TIMER),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field):
                    self.update_use_case.execute(
                        UpdateCallDTO(call.id, {field: value})
                    )

        self.assertEqual(len(self.timeline.events), 1)  # only CALL_LOGGED

    def test_update_rejects_unknown_fields(self):
        call = self.log_lead_call()

        with self.assertRaisesRegex(ValueError, "owner_id"):
            self.update_use_case.execute(
                UpdateCallDTO(call.id, {"owner_id": uuid4()})
            )

    def test_update_revalidates_and_leaves_call_untouched_on_error(self):
        call = self.log_lead_call(description="note")
        self.timeline.events.clear()
        saves_before = self.repo.save_count

        for fields, message in (
            ({"duration_seconds": 86401}, "duration"),
            ({"description": "x" * 1001}, "1000"),
            ({"call_start_time": None}, "start time is required"),
            (
                {
                    "call_start_time": datetime.now(timezone.utc)
                    + timedelta(hours=1)
                },
                "future",
            ),
            ({"outcome": "Exploded"}, "outcome"),
        ):
            with self.subTest(fields=fields):
                with self.assertRaisesRegex(ValueError, message):
                    self.update_use_case.execute(UpdateCallDTO(call.id, fields))

        stored = self.repo.calls[call.id]
        self.assertEqual(stored.duration_seconds, 250)
        self.assertEqual(stored.description, "note")
        self.assertEqual(stored.outcome, CallOutcome.CONNECTED)
        self.assertEqual(self.repo.save_count, saves_before)
        self.assertEqual(self.timeline.events, [])

    def test_update_missing_or_deleted_call(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            self.update_use_case.execute(UpdateCallDTO(uuid4(), {}))

        call = self.log_lead_call()
        self.delete_use_case.execute(call.id)

        with self.assertRaisesRegex(ValueError, "not found"):
            self.update_use_case.execute(
                UpdateCallDTO(call.id, {"outcome": CallOutcome.BUSY})
            )

    def test_only_the_latest_call_of_a_record_can_be_updated(self):
        older = self.log_lead_call(call_start_time=started(120), description="old")
        latest = self.log_lead_call(call_start_time=started(10), description="new")
        # A call on another record never affects which call is the latest.
        other_contact_call = self.log_contact_call(call_start_time=started(300))
        self.timeline.events.clear()
        saves_before = self.repo.save_count

        with self.assertRaisesRegex(ValueError, "Only the latest call"):
            self.update_use_case.execute(
                UpdateCallDTO(older.id, {"outcome": CallOutcome.BUSY})
            )

        self.assertEqual(self.repo.calls[older.id].outcome, CallOutcome.CONNECTED)
        self.assertEqual(self.repo.save_count, saves_before)
        self.assertEqual(self.timeline.events, [])

        updated = self.update_use_case.execute(
            UpdateCallDTO(latest.id, {"outcome": CallOutcome.BUSY})
        )
        self.assertEqual(updated.outcome, CallOutcome.BUSY)

        updated = self.update_use_case.execute(
            UpdateCallDTO(other_contact_call.id, {"outcome": CallOutcome.BUSY})
        )
        self.assertEqual(updated.outcome, CallOutcome.BUSY)

    def test_previous_call_becomes_updatable_again_when_latest_is_deleted(self):
        older = self.log_lead_call(call_start_time=started(120))
        latest = self.log_lead_call(call_start_time=started(10))

        self.delete_use_case.execute(latest.id)

        updated = self.update_use_case.execute(
            UpdateCallDTO(older.id, {"outcome": CallOutcome.BUSY})
        )
        self.assertEqual(updated.outcome, CallOutcome.BUSY)

    def test_detail_reports_whether_the_call_is_the_latest(self):
        older = self.log_lead_call(call_start_time=started(120))
        latest = self.log_lead_call(call_start_time=started(10))
        only = self.log_contact_call(call_start_time=started(60))

        self.assertFalse(self.detail_use_case.execute(older.id).is_latest)
        self.assertTrue(self.detail_use_case.execute(latest.id).is_latest)
        self.assertTrue(self.detail_use_case.execute(only.id).is_latest)

    # -- delete -------------------------------------------------------------

    def test_delete_soft_deletes_and_records_timeline(self):
        call = self.log_contact_call(account_id=self.account.id)
        self.timeline.events.clear()

        self.delete_use_case.execute(call.id, current_user_id=self.user.id)

        self.assertTrue(self.repo.calls[call.id].is_deleted)
        self.assertIsNone(self.repo.get_by_id(call.id))

        event = self.timeline.events[0]
        self.assertEqual(event["event_type"], "CALL_DELETED")
        self.assertEqual(event["actor_id"], self.user.id)
        self.assertEqual(
            event["targets"],
            [
                ("CALL", call.id),
                ("CONTACT", self.contact.id),
                ("ACCOUNT", self.account.id),
            ],
        )

    def test_delete_missing_or_already_deleted_call(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            self.delete_use_case.execute(uuid4())

        call = self.log_lead_call()
        self.delete_use_case.execute(call.id)

        with self.assertRaisesRegex(ValueError, "not found"):
            self.delete_use_case.execute(call.id)

    # -- list ---------------------------------------------------------------

    def test_get_calls_delegates_to_repository(self):
        self.log_lead_call(call_start_time=started(60))
        newest = self.log_lead_call(call_start_time=started(5))
        deleted = self.log_lead_call(call_start_time=started(1))
        self.delete_use_case.execute(deleted.id)

        result = GetCallsUseCase(self.repo).execute(ListQuery())

        self.assertEqual(result.total, 2)
        self.assertEqual(result.results[0].call.id, newest.id)

    # -- detail -------------------------------------------------------------

    def test_detail_for_lead_call(self):
        oldest = self.log_lead_call(call_start_time=started(300))
        middle = self.log_lead_call(call_start_time=started(100))
        current = self.log_lead_call(call_start_time=started(50))
        self.log_contact_call()  # call of another record
        self.timeline_repo.history[("CALL", current.id)] = [
            {"event_type": "CALL_UPDATED", "metadata": {"changes": {}}},
            {"event_type": "CALL_LOGGED", "metadata": {}},
        ]

        detail = self.detail_use_case.execute(current.id)

        self.assertEqual(detail.call.call.id, current.id)
        self.assertEqual(detail.related_record_type, "LEAD")
        self.assertEqual(detail.related_record_id, self.lead.id)
        self.assertEqual(detail.related_record_name, "Acme Lead")
        self.assertEqual(
            detail.change_history,
            self.timeline_repo.history[("CALL", current.id)],
        )
        self.assertEqual(self.timeline_repo.requested, [("CALL", current.id)])
        # other calls of the same lead, newest first, current call excluded
        self.assertEqual(
            [c.call.id for c in detail.related_calls],
            [middle.id, oldest.id],
        )
        self.assertNotIn(current.id, [c.call.id for c in detail.related_calls])
        self.assertEqual(detail.total_calls_for_record, 3)

    def test_detail_for_contact_call(self):
        older = self.log_contact_call(call_start_time=started(200))
        current = self.log_contact_call(call_start_time=started(20))
        self.log_lead_call()  # call of another record
        self.timeline_repo.history[("CALL", current.id)] = [
            {"event_type": "CALL_LOGGED", "metadata": {}},
        ]

        detail = self.detail_use_case.execute(current.id)

        self.assertEqual(detail.related_record_type, "CONTACT")
        self.assertEqual(detail.related_record_id, self.contact.id)
        self.assertEqual(detail.related_record_name, "Jane Contact")
        self.assertEqual(len(detail.change_history), 1)
        self.assertEqual([c.call.id for c in detail.related_calls], [older.id])
        self.assertEqual(detail.total_calls_for_record, 2)

    def test_detail_with_no_other_calls(self):
        only = self.log_lead_call()

        detail = self.detail_use_case.execute(only.id)

        self.assertEqual(detail.related_calls, [])
        self.assertEqual(detail.total_calls_for_record, 1)
        self.assertEqual(detail.change_history, [])

    def test_detail_related_calls_are_capped_at_fifty(self):
        for minutes in range(60):
            self.log_lead_call(call_start_time=started(minutes + 10))
        current = self.log_lead_call(call_start_time=started(1))

        detail = self.detail_use_case.execute(current.id)

        self.assertEqual(len(detail.related_calls), 50)
        self.assertEqual(detail.total_calls_for_record, 61)

    def test_detail_ignores_deleted_calls(self):
        current = self.log_lead_call(call_start_time=started(50))
        gone = self.log_lead_call(call_start_time=started(100))
        self.delete_use_case.execute(gone.id)

        detail = self.detail_use_case.execute(current.id)

        self.assertEqual(detail.related_calls, [])
        self.assertEqual(detail.total_calls_for_record, 1)
        self.assertIsNone(self.detail_use_case.execute(gone.id))

    def test_detail_returns_none_for_unknown_call(self):
        self.assertIsNone(self.detail_use_case.execute(uuid4()))

    # -- repository contract (soft delete by record) ------------------------

    def test_soft_delete_by_record_returns_deleted_ids(self):
        lead_call_1 = self.log_lead_call()
        lead_call_2 = self.log_lead_call()
        contact_call = self.log_contact_call()
        already_deleted = self.log_lead_call()
        self.delete_use_case.execute(already_deleted.id)

        ids = self.repo.soft_delete_by_lead_id(self.lead.id)

        self.assertEqual(set(ids), {lead_call_1.id, lead_call_2.id})
        self.assertIsNotNone(self.repo.get_by_id(contact_call.id))

        self.assertEqual(
            self.repo.soft_delete_by_contact_id(self.contact.id),
            [contact_call.id],
        )
        self.assertEqual(self.repo.soft_delete_by_lead_id(self.lead.id), [])

    def test_unlink_account_keeps_contact_calls(self):
        call = self.log_contact_call(account_id=self.account.id)

        self.repo.unlink_account_from_contact_calls(self.account.id)

        self.assertIsNone(self.repo.get_by_id(call.id).account_id)
        self.assertFalse(self.repo.get_by_id(call.id).is_deleted)


if __name__ == "__main__":
    unittest.main()
