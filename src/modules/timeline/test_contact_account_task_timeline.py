from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from django.test import TestCase
from src.modules.accounts.domain.entities.account import Account

from src.modules.accounts.application.dto.update_account import UpdateAccountDTO
from src.modules.accounts.application.use_cases.update_account import UpdateAccountUseCase
from src.modules.contacts.application.dto.update_contact import UpdateContactDTO
from src.modules.contacts.application.use_cases.update_contact import UpdateContactUseCase
from src.modules.tasks.application.dto.update_task import UpdateTaskDTO
from src.modules.tasks.application.use_cases.update_task import UpdateTaskUseCase
from src.modules.tasks.domain.enums.task_priority import TaskPriority
from src.modules.tasks.domain.enums.task_status import TaskStatus
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User


class RecordingTimelineRecorder:
    def __init__(self):
        self.events = []

    def record(self, **kwargs):
        self.events.append(kwargs)


class ImmediateTransactionManager:
    def execute(self, operation):
        return operation()


class InMemoryRepository:
    def __init__(self, item):
        self.item = item

    def get_by_id(self, item_id):
        return self.item if self.item is not None and self.item.id == item_id else None

    def save(self, item):
        self.item = item
        return item


class InMemoryCollectionRepository:
    def __init__(self, items):
        self.items = {item.id: item for item in items}

    def get_by_id(self, item_id):
        return self.items.get(item_id)

    def save(self, item):
        self.items[item.id] = item
        return item


class InMemoryUserRepository:
    def __init__(self, user):
        self.user = user

    def get_by_id(self, user_id):
        return self.user if self.user.id == user_id else None


class ContactAccountTaskTimelineTests(TestCase):
    def setUp(self):
        self.user_id = uuid4()
        self.user = User(
            id=self.user_id,
            name="Don Davis",
            email="don@example.com",
            role=UserRole.ADMIN,
            is_active=True,
            created_at=None,
            updated_at=None,
        )

    def _contact(self):
        return SimpleNamespace(
            id=uuid4(),
            account_id=None,
            contact_owner_id=self.user_id,
            name="John Doe",
            email="old@example.com",
            secondary_email=None,
            phone=None,
            other_phone=None,
            mobile="1111111111",
            home_phone=None,
            assistant_phone=None,
            title="Manager",
            department=None,
            lead_source=None,
            vendor_name=None,
            date_of_birth=date(1990, 1, 1),
            assistant=None,
            email_opt_out=False,
            reporting_to_id=None,
            mailing_address=None,
            mailing_city=None,
            mailing_state=None,
            mailing_country=None,
            mailing_postal_code=None,
            other_address=None,
            description=None,
            modified_by_id=self.user_id,
            updated_at=None,
        )

    def _account(self):
        return SimpleNamespace(
            id=uuid4(),
            account_name="ABC Pvt Ltd",
            account_site=None,
            account_number="ACC-001",
            account_type="Customer",
            industry=None,
            annual_revenue=100000,
            rating=None,
            phone="1111111111",
            website=None,
            ticker_symbol=None,
            ownership="None",
            employees=10,
            sic_code=None,
            billing_address=None,
            billing_city="Kochi",
            billing_state="Kerala",
            billing_country="India",
            billing_postal_code="682001",
            description=None,
            modified_by_id=self.user_id,
            updated_at=None,
            is_deleted=False,
        )

    def _account_dto(self, account_id, **overrides):
        values = {
            "account_id": account_id,
            "account_name": "ABC Pvt Ltd",
            "account_site": None,
            "account_number": "ACC-001",
            "account_type": "Customer",
            "industry": None,
            "annual_revenue": 100000,
            "rating": None,
            "phone": "2222222222",
            "website": None,
            "ticker_symbol": None,
            "ownership": "None",
            "employees": 10,
            "sic_code": None,
            "billing_address": None,
            "billing_city": "Kochi",
            "billing_state": "Kerala",
            "billing_country": "India",
            "billing_postal_code": "682001",
            "description": None,
        }
        values.update(overrides)
        return UpdateAccountDTO(**values)

    def test_contact_update_timeline_contains_only_changed_fields(self):
        contact = self._contact()
        recorder = RecordingTimelineRecorder()
        use_case = UpdateContactUseCase(
            contact_repository=InMemoryRepository(contact),
            account_repository=InMemoryRepository(None),
            user_repository=InMemoryUserRepository(self.user),
            timeline_recorder=recorder,
            transaction_manager=ImmediateTransactionManager(),
        )

        use_case.execute(
            UpdateContactDTO(
                contact_id=contact.id,
                fields={
                    "name": "John Doe",
                    "email": "new@example.com",
                },
            ),
            current_user_id=self.user_id,
        )

        self.assertEqual(len(recorder.events), 1)
        event = recorder.events[0]
        self.assertEqual(
            event["metadata"]["changes"],
            {
                "email": {
                    "old_value": "old@example.com",
                    "new_value": "new@example.com",
                }
            },
        )
        self.assertIn("Email: old@example.com → new@example.com", event["message"])
        self.assertNotIn("Name:", event["message"])

    def test_contact_relationship_changes_use_names_not_uuids(self):
        contact = self._contact()
        account = self._account()
        reporting_contact = self._contact()
        reporting_contact.name = "Reporting Contact"
        contact_repository = InMemoryCollectionRepository([contact, reporting_contact])
        account_repository = InMemoryRepository(account)
        owner = User(
            id=uuid4(),
            name="Jane Owner",
            email="jane@example.com",
            role=UserRole.ADMIN,
            is_active=True,
            created_at=None,
            updated_at=None,
        )
        user_repository = InMemoryCollectionRepository([self.user, owner])
        recorder = RecordingTimelineRecorder()

        use_case = UpdateContactUseCase(
            contact_repository=contact_repository,
            account_repository=account_repository,
            user_repository=user_repository,
            timeline_recorder=recorder,
            transaction_manager=ImmediateTransactionManager(),
        )

        use_case.execute(
            UpdateContactDTO(
                contact_id=contact.id,
                fields={
                    "account_id": account.id,
                    "contact_owner_id": owner.id,
                    "reporting_to_id": reporting_contact.id,
                },
            ),
            current_user_id=self.user_id,
        )

        event = recorder.events[0]
        changes = event["metadata"]["changes"]
        self.assertEqual(changes["account_id"], {"old_value": None, "new_value": account.account_name})
        self.assertEqual(changes["contact_owner_id"], {"old_value": self.user.name, "new_value": owner.name})
        self.assertEqual(changes["reporting_to_id"], {"old_value": None, "new_value": reporting_contact.name})
        self.assertIn(f"Account: None → {account.account_name}", event["message"])
        self.assertNotIn(str(account.id), event["message"])
        self.assertNotIn(str(owner.id), event["message"])
        self.assertNotIn(str(reporting_contact.id), event["message"])

    def test_account_update_timeline_contains_only_changed_fields(self):
        account = self._account()
        recorder = RecordingTimelineRecorder()
        use_case = UpdateAccountUseCase(
            account_repository=InMemoryRepository(account),
            timeline_recorder=recorder,
            transaction_manager=ImmediateTransactionManager(),
        )

        use_case.execute(
            self._account_dto(account.id),
            current_user_id=self.user_id,
        )

        self.assertEqual(len(recorder.events), 1)
        event = recorder.events[0]
        self.assertEqual(
            event["metadata"]["changes"],
            {
                "phone": {
                    "old_value": "1111111111",
                    "new_value": "2222222222",
                }
            },
        )
        self.assertIn("Phone: 1111111111 → 2222222222", event["message"])
        self.assertNotIn("Billing City:", event["message"])

    def test_task_owner_change_uses_user_name_not_uuid(self):
        task = SimpleNamespace(
            id=uuid4(),
            subject="Prepare business proposal",
            due_date=None,
            priority=TaskPriority.NORMAL,
            owner_id=self.user_id,
            reminder_at=None,
            lead_id=None,
            contact_id=None,
            account_id=None,
            status=TaskStatus.NOT_STARTED,
            description=None,
            is_deleted=False,
        )
        new_owner = User(
            id=uuid4(),
            name="Jane Owner",
            email="jane@example.com",
            role=UserRole.ADMIN,
            is_active=True,
            created_at=None,
            updated_at=None,
        )
        recorder = RecordingTimelineRecorder()

        use_case = UpdateTaskUseCase(
            task_repository=InMemoryRepository(task),
            user_repository=InMemoryCollectionRepository([self.user, new_owner]),
            lead_repository=InMemoryRepository(None),
            contact_repository=InMemoryRepository(None),
            account_repository=InMemoryRepository(None),
            timeline_recorder=recorder,
            transaction_manager=ImmediateTransactionManager(),
        )

        use_case.execute(
            UpdateTaskDTO(task_id=task.id, fields={"owner_id": new_owner.id}),
            current_user_id=self.user_id,
        )

        event = recorder.events[0]
        self.assertEqual(
            event["metadata"]["changes"]["owner_id"],
            {"old_value": self.user.name, "new_value": new_owner.name},
        )
        self.assertIn("Task Owner: Don Davis → Jane Owner", event["message"])
        self.assertNotIn(str(new_owner.id), event["message"])

    def test_task_lead_relationship_change_uses_lead_name_not_uuid(self):
        task = SimpleNamespace(
            id=uuid4(),
            subject="Prepare business proposal",
            due_date=None,
            priority=TaskPriority.NORMAL,
            owner_id=self.user_id,
            reminder_at=None,
            lead_id=None,
            contact_id=None,
            account_id=None,
            status=TaskStatus.NOT_STARTED,
            description=None,
            is_deleted=False,
        )
        lead = SimpleNamespace(id=uuid4(), name="AAthish", is_deleted=False)
        recorder = RecordingTimelineRecorder()

        use_case = UpdateTaskUseCase(
            task_repository=InMemoryRepository(task),
            user_repository=InMemoryUserRepository(self.user),
            lead_repository=InMemoryRepository(lead),
            contact_repository=InMemoryRepository(None),
            account_repository=InMemoryRepository(None),
            timeline_recorder=recorder,
            transaction_manager=ImmediateTransactionManager(),
        )

        use_case.execute(
            UpdateTaskDTO(task_id=task.id, fields={"lead_id": lead.id}),
            current_user_id=self.user_id,
        )

        event = recorder.events[0]
        self.assertEqual(
            event["metadata"]["changes"]["lead_id"],
            {"old_value": None, "new_value": "AAthish"},
        )
        self.assertIn("Lead: None → AAthish", event["message"])
        self.assertNotIn(str(lead.id), event["message"])

    def test_task_contact_and_account_relationship_changes_use_names_not_uuids(self):
        task = SimpleNamespace(
            id=uuid4(),
            subject="Prepare business proposal",
            due_date=None,
            priority=TaskPriority.NORMAL,
            owner_id=self.user_id,
            reminder_at=None,
            lead_id=None,
            contact_id=None,
            account_id=None,
            status=TaskStatus.NOT_STARTED,
            description=None,
            is_deleted=False,
        )
        contact = SimpleNamespace(id=uuid4(), name="John Doe", is_deleted=False)
        account = SimpleNamespace(id=uuid4(), account_name="ABC Pvt Ltd", is_deleted=False)
        recorder = RecordingTimelineRecorder()

        use_case = UpdateTaskUseCase(
            task_repository=InMemoryRepository(task),
            user_repository=InMemoryUserRepository(self.user),
            lead_repository=InMemoryRepository(None),
            contact_repository=InMemoryRepository(contact),
            account_repository=InMemoryRepository(account),
            timeline_recorder=recorder,
            transaction_manager=ImmediateTransactionManager(),
        )

        use_case.execute(
            UpdateTaskDTO(
                task_id=task.id,
                fields={"contact_id": contact.id, "account_id": account.id},
            ),
            current_user_id=self.user_id,
        )

        event = recorder.events[0]
        changes = event["metadata"]["changes"]
        self.assertEqual(changes["contact_id"], {"old_value": None, "new_value": contact.name})
        self.assertEqual(changes["account_id"], {"old_value": None, "new_value": account.account_name})
        self.assertNotIn(str(contact.id), event["message"])
        self.assertNotIn(str(account.id), event["message"])

    def test_task_update_timeline_contains_subject_task_id_and_changed_fields(self):
        task = SimpleNamespace(
            id=uuid4(),
            subject="Prepare business proposal",
            due_date=None,
            priority=TaskPriority.NORMAL,
            owner_id=self.user_id,
            reminder_at=None,
            lead_id=uuid4(),
            contact_id=None,
            account_id=None,
            status=TaskStatus.NOT_STARTED,
            description=None,
            is_deleted=False,
        )
        lead = SimpleNamespace(id=task.lead_id, is_deleted=False)
        recorder = RecordingTimelineRecorder()

        use_case = UpdateTaskUseCase(
            task_repository=InMemoryRepository(task),
            user_repository=InMemoryUserRepository(self.user),
            lead_repository=InMemoryRepository(lead),
            contact_repository=InMemoryRepository(None),
            account_repository=InMemoryRepository(None),
            timeline_recorder=recorder,
            transaction_manager=ImmediateTransactionManager(),
        )

        use_case.execute(
            UpdateTaskDTO(
                task_id=task.id,
                fields={"priority": TaskPriority.HIGH},
            ),
            current_user_id=self.user_id,
        )

        self.assertEqual(len(recorder.events), 1)
        event = recorder.events[0]
        self.assertEqual(event["event_type"], "TASK_UPDATED")
        self.assertEqual(event["metadata"]["task_id"], str(task.id))
        self.assertEqual(event["metadata"]["subject"], "Prepare business proposal")
        self.assertEqual(
            event["metadata"]["changes"],
            {
                "priority": {
                    "old_value": "Normal",
                    "new_value": "High",
                }
            },
        )
        self.assertIn("Task Prepare business proposal was updated.", event["message"])
        self.assertIn("Priority: Normal → High", event["message"])
