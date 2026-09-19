from django.test import TestCase
from django.utils import timezone

from src.modules.accounts.application.dto.delete_account import DeleteAccountDTO
from src.modules.accounts.application.use_cases.delete_account import DeleteAccountUseCase
from src.modules.accounts.infrastructure.persistence.django_account_model import DjangoAccountModel
from src.modules.accounts.infrastructure.persistence.django_account_repository import DjangoAccountRepository
from src.modules.contacts.application.dto.delete_contact import DeleteContactDTO
from src.modules.contacts.application.use_cases.delete_contact import DeleteContactUseCase
from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.contacts.infrastructure.persistence.django_contact_model import DjangoContactModel
from src.modules.leads.application.use_cases.delete_lead import DeleteLeadUseCase
from src.modules.leads.infrastructure.persistence.django_lead_model import DjangoLeadModel
from src.modules.leads.infrastructure.persistence.django_lead_repository import DjangoLeadRepository
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.tasks.infrastructure.persistence.django_task_repository import DjangoTaskRepository
from src.modules.tasks.infrastructure.persistence.models import DjangoTaskModel
from src.modules.timeline.domain.enums.timeline_entity_type import TimelineEntityType
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.persistence.models import TimelineEvent, TimelineEventTarget
from src.modules.users.infrastructure.persistence.models import User


class TimelineCascadeDeletionTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.user = User.objects.create_user(
            email="timeline-cascade@example.com",
            password="password",
            name="Timeline Cascade",
            role=User.Role.ADMIN,
        )
        self.lead = DjangoLeadModel.objects.create(
            name="Cascade Lead",
            company_name="Lead Company",
            owner=self.user,
        )
        self.account = DjangoAccountModel.objects.create(
            account_owner=self.user,
            account_name="Cascade Account",
            created_by=self.user,
            created_at=now,
            modified_by=self.user,
            updated_at=now,
        )
        self.contact = DjangoContactModel.objects.create(
            account=self.account,
            contact_owner=self.user,
            name="Cascade Contact",
            created_by=self.user,
            created_at=now,
            modified_by=self.user,
            updated_at=now,
        )

    def _event(self, targets, message="event"):
        event = TimelineEvent.objects.create(
            event_type="TEST_EVENT",
            actor=self.user,
            message=message,
            metadata={},
        )
        TimelineEventTarget.objects.bulk_create([
            TimelineEventTarget(
                event=event,
                entity_type=entity_type,
                entity_id=entity_id,
            )
            for entity_type, entity_id in targets
        ])
        return event

    def _task(self, **kwargs):
        return DjangoTaskModel.objects.create(
            subject=kwargs.pop("subject", "Cascade task"),
            owner=self.user,
            created_by=self.user,
            **kwargs,
        )

    def test_lead_delete_soft_deletes_tasks_and_timeline(self):
        task = self._task(lead=self.lead)
        event = self._event([(TimelineEntityType.LEAD.value, self.lead.id)])

        DeleteLeadUseCase(
            DjangoLeadRepository(),
            DjangoTaskRepository(),
            DjangoTimelineRepository(),
            DjangoTransactionManager(),
        ).execute(self.lead.id)

        self.lead.refresh_from_db()
        task.refresh_from_db()
        event.refresh_from_db()
        target = TimelineEventTarget.objects.get(event=event)

        self.assertTrue(self.lead.is_deleted)
        self.assertTrue(task.is_deleted)
        self.assertTrue(event.is_deleted)
        self.assertTrue(target.is_deleted)
        self.assertEqual(
            DjangoTimelineRepository().get_for_entity(
                TimelineEntityType.LEAD.value,
                self.lead.id,
            ),
            [],
        )

    def test_contact_delete_soft_deletes_tasks_and_timeline(self):
        task = self._task(contact=self.contact)
        event = self._event([(TimelineEntityType.CONTACT.value, self.contact.id)])

        DeleteContactUseCase(
            DjangoContactRepository(),
            DjangoTaskRepository(),
            DjangoTimelineRepository(),
            DjangoTransactionManager(),
        ).execute(DeleteContactDTO(contact_id=self.contact.id))

        self.contact.refresh_from_db()
        task.refresh_from_db()
        event.refresh_from_db()
        target = TimelineEventTarget.objects.get(event=event)
        self.account.refresh_from_db()

        self.assertTrue(self.contact.is_deleted)
        self.assertIsNone(self.contact.account_id)
        self.assertTrue(task.is_deleted)
        self.assertTrue(event.is_deleted)
        self.assertTrue(target.is_deleted)
        self.assertFalse(self.account.is_deleted)
        self.assertEqual(
            DjangoTimelineRepository().get_for_entity(
                TimelineEntityType.CONTACT.value,
                self.contact.id,
            ),
            [],
        )

    def test_account_delete_keeps_contact_task_and_contact_timeline_target(self):
        task = self._task(contact=self.contact, account=self.account)
        event = self._event([
            (TimelineEntityType.CONTACT.value, self.contact.id),
            (TimelineEntityType.ACCOUNT.value, self.account.id),
        ])

        DeleteAccountUseCase(
            DjangoAccountRepository(),
            DjangoContactRepository(),
            DjangoTaskRepository(),
            DjangoTimelineRepository(),
            DjangoTransactionManager(),
        ).execute(
            DeleteAccountDTO(account_id=self.account.id),
            self.user.id,
        )

        self.account.refresh_from_db()
        self.contact.refresh_from_db()
        task.refresh_from_db()
        event.refresh_from_db()
        account_target = TimelineEventTarget.objects.get(
            event=event,
            entity_type=TimelineEntityType.ACCOUNT.value,
        )
        contact_target = TimelineEventTarget.objects.get(
            event=event,
            entity_type=TimelineEntityType.CONTACT.value,
        )

        self.assertTrue(self.account.is_deleted)
        self.assertFalse(self.contact.is_deleted)
        self.assertIsNone(self.contact.account_id)
        self.assertFalse(task.is_deleted)
        self.assertIsNone(task.account_id)
        self.assertFalse(event.is_deleted)
        self.assertTrue(account_target.is_deleted)
        self.assertFalse(contact_target.is_deleted)

        contact_timeline = DjangoTimelineRepository().get_for_entity(
            TimelineEntityType.CONTACT.value,
            self.contact.id,
        )
        self.assertEqual(len(contact_timeline), 1)
        self.assertEqual(
            contact_timeline[0]["targets"],
            [{"entity_type": "CONTACT", "entity_id": self.contact.id}],
        )

    def test_account_only_legacy_task_is_soft_deleted(self):
        task = self._task(account=self.account)

        DeleteAccountUseCase(
            DjangoAccountRepository(),
            DjangoContactRepository(),
            DjangoTaskRepository(),
            DjangoTimelineRepository(),
            DjangoTransactionManager(),
        ).execute(
            DeleteAccountDTO(account_id=self.account.id),
            self.user.id,
        )

        task.refresh_from_db()
        self.assertTrue(task.is_deleted)
    def test_lead_delete_rolls_back_when_timeline_cascade_fails(self):
        task = self._task(lead=self.lead)

        class FailingTimelineRepository:
            def soft_delete_by_entity(self, entity_type, entity_id):
                raise RuntimeError("timeline cascade failed")

        use_case = DeleteLeadUseCase(
            DjangoLeadRepository(),
            DjangoTaskRepository(),
            FailingTimelineRepository(),
            DjangoTransactionManager(),
        )

        with self.assertRaises(RuntimeError):
            use_case.execute(self.lead.id)

        self.lead.refresh_from_db()
        task.refresh_from_db()

        self.assertFalse(self.lead.is_deleted)
        self.assertFalse(task.is_deleted)

