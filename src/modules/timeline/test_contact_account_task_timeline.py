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
