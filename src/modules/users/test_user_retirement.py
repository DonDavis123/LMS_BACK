from datetime import timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.meetings.infrastructure.persistence.models import (
    DjangoMeetingModel,
    DjangoMeetingParticipantModel,
)
from src.modules.notifications.infrastructure.persistence.models import (
    DjangoNotificationModel,
)
from src.modules.reminders.infrastructure.persistence.models import (
    DjangoReminderModel,
)
from src.modules.shared.application.dto.list_query import ListQuery
from src.modules.tasks.infrastructure.persistence.models import DjangoTaskModel
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import (
    DjangoTimelineRepository,
)
from src.modules.timeline.infrastructure.persistence.models import TimelineEvent
from src.modules.users.application.use_cases.delete_user import DeleteUserUseCase
from src.modules.users.application.use_cases.unblock_user import UnblockUserUseCase
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User as DomainUser
from src.modules.users.infrastructure.persistence.models import User
from src.modules.shared.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)
from src.modules.users.infrastructure.persistence.user_audit_log_repository import (
    DjangoUserAuditLogRepository,
)
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)
from src.modules.users.presentation.api.dependencies.user_dependencies import (
    get_delete_user_use_case,
)


def domain_user(role=UserRole.ADMIN, is_active=True, deleted_at=None):
    now = timezone.now()
    return DomainUser(
        id=uuid4(),
        name="User",
        email=f"{uuid4()}@example.com",
        role=role,
        is_active=is_active,
        created_at=now,
        updated_at=now,
        deleted_at=deleted_at,
    )


class DeleteUserValidationTests(SimpleTestCase):
    """Application-level validation and orchestration (no database)."""

    def setUp(self):
        self.superadmin = domain_user(UserRole.SUPERADMIN)
        self.target = domain_user()
        self.replacement = domain_user()
        self.users = {
            u.id: u for u in (self.superadmin, self.target, self.replacement)
        }

        self.user_repository = Mock()
        self.user_repository.get_by_id.side_effect = self.users.get
        self.lead_repository = Mock()
        self.contact_repository = Mock()
        self.account_repository = Mock()
        self.meeting_repository = Mock()
        self.task_repository = Mock()
        self.reminder_repository = Mock()
        self.notification_repository = Mock()
        self.audit_log_repository = Mock()
        self.session_revoker = Mock()
        self.transaction_manager = Mock()
        self.transaction_manager.execute.side_effect = lambda op: op()
        # By default the target owns records, so a transfer is required.
        for repository in (
            self.lead_repository,
            self.contact_repository,
            self.account_repository,
            self.meeting_repository,
        ):
            repository.count_by_owner_id.return_value = 1
            repository.count_by_host_id.return_value = 1

        self.use_case = DeleteUserUseCase(
            self.user_repository,
            self.lead_repository,
            self.contact_repository,
            self.account_repository,
            self.meeting_repository,
            self.task_repository,
            self.reminder_repository,
            self.notification_repository,
            self.audit_log_repository,
            self.session_revoker,
            self.transaction_manager,
        )

    def _assert_nothing_changed(self, in_transaction=False):
        if not in_transaction:
            self.transaction_manager.execute.assert_not_called()
        self.lead_repository.transfer_ownership.assert_not_called()
        self.contact_repository.transfer_ownership.assert_not_called()
        self.account_repository.transfer_ownership.assert_not_called()
        self.meeting_repository.transfer_host.assert_not_called()
        self.task_repository.delete_by_owner_id.assert_not_called()
        self.reminder_repository.delete_by_user_id.assert_not_called()
        self.notification_repository.delete_by_user_id.assert_not_called()
        self.user_repository.soft_delete.assert_not_called()

    def _fail(self, replacement_user_id, message, user_id=None, in_transaction=False):
        with self.assertRaisesMessage(ValueError, message):
            self.use_case.execute(
                self.superadmin,
                user_id or self.target.id,
                replacement_user_id,
            )
        self._assert_nothing_changed(in_transaction=in_transaction)

    def test_replacement_user_is_required_when_records_must_be_transferred(self):
        # The decision is made inside the transaction, before any change.
        self._fail(None, "Replacement user is required.", in_transaction=True)

    def test_replacement_user_is_required_for_each_kind_of_record(self):
        repositories = (
            (self.lead_repository, "count_by_owner_id"),
            (self.contact_repository, "count_by_owner_id"),
            (self.account_repository, "count_by_owner_id"),
            (self.meeting_repository, "count_by_host_id"),
        )
        for owning_repository, method in repositories:
            with self.subTest(repository=method, mock=id(owning_repository)):
                for repository, _ in repositories:
                    getattr(repository, method).return_value = 0
                getattr(owning_repository, method).return_value = 1
                self._fail(None, "Replacement user is required.", in_transaction=True)

    def test_replacement_user_is_optional_when_nothing_to_transfer(self):
        for repository, method in (
            (self.lead_repository, "count_by_owner_id"),
            (self.contact_repository, "count_by_owner_id"),
            (self.account_repository, "count_by_owner_id"),
            (self.meeting_repository, "count_by_host_id"),
        ):
            getattr(repository, method).return_value = 0
        self.user_repository.soft_delete.return_value = self.target

        self.use_case.execute(self.superadmin, self.target.id, None)

        self.lead_repository.transfer_ownership.assert_not_called()
        self.contact_repository.transfer_ownership.assert_not_called()
        self.account_repository.transfer_ownership.assert_not_called()
        self.meeting_repository.transfer_host.assert_not_called()
        self.task_repository.delete_by_owner_id.assert_called_once_with(self.target.id)
        self.reminder_repository.delete_by_user_id.assert_called_once_with(self.target.id)
        self.notification_repository.delete_by_user_id.assert_called_once_with(self.target.id)
        self.user_repository.soft_delete.assert_called_once()
        self.audit_log_repository.add.assert_called_once()
        self.session_revoker.revoke_all_sessions.assert_called_once_with(self.target.id)

    def test_supplied_replacement_is_still_validated_when_nothing_to_transfer(self):
        for repository, method in (
            (self.lead_repository, "count_by_owner_id"),
            (self.contact_repository, "count_by_owner_id"),
            (self.account_repository, "count_by_owner_id"),
            (self.meeting_repository, "count_by_host_id"),
        ):
            getattr(repository, method).return_value = 0
        self.replacement.is_active = False

        self._fail(self.replacement.id, "Replacement user must be active.")

    def test_replacement_user_does_not_exist(self):
        self._fail(uuid4(), "Replacement user not found.")

    def test_replacement_user_inactive(self):
        self.replacement.is_active = False
        self._fail(self.replacement.id, "Replacement user must be active.")

    def test_replacement_user_soft_deleted(self):
        self.replacement.deleted_at = timezone.now()
        self.replacement.is_active = False
        self._fail(self.replacement.id, "Replacement user has been deleted.")

    def test_replacement_user_same_as_target(self):
        self._fail(
            self.target.id,
            "Replacement user must be different from the user being deleted.",
        )

    def test_replacement_user_with_invalid_role(self):
        for role in (UserRole.SALES_MANAGER, UserRole.SALES_EXECUTIVE):
            with self.subTest(role=role):
                self.replacement.role = role
                self._fail(
                    self.replacement.id,
                    "Replacement user must be an Admin or Superadmin.",
                )

    def test_target_user_does_not_exist(self):
        self._fail(self.replacement.id, "User not found.", user_id=uuid4())

    def test_target_user_already_soft_deleted(self):
        self.target.deleted_at = timezone.now()
        self._fail(self.replacement.id, "User has already been deleted.")

    def test_only_active_superadmin_can_delete(self):
        for actor in (domain_user(UserRole.ADMIN), domain_user(UserRole.SALES_MANAGER)):
            with self.subTest(role=actor.role):
                with self.assertRaises(ValueError):
                    self.use_case.execute(actor, self.target.id, self.replacement.id)
        self.superadmin.is_active = False
        with self.assertRaises(ValueError):
            self.use_case.execute(self.superadmin, self.target.id, self.replacement.id)
        self._assert_nothing_changed()

    def test_superadmin_cannot_delete_self(self):
        self._fail(
            self.replacement.id,
            "A superadmin cannot delete their own account.",
            user_id=self.superadmin.id,
        )

    def test_orchestration_runs_in_one_transaction_and_never_hard_deletes(self):
        self.user_repository.soft_delete.return_value = self.target

        self.use_case.execute(self.superadmin, self.target.id, self.replacement.id)

        self.transaction_manager.execute.assert_called_once()
        kwargs = dict(from_user_id=self.target.id, to_user_id=self.replacement.id)
        self.lead_repository.transfer_ownership.assert_called_once_with(**kwargs)
        self.contact_repository.transfer_ownership.assert_called_once_with(**kwargs)
        self.account_repository.transfer_ownership.assert_called_once_with(**kwargs)
        self.meeting_repository.transfer_host.assert_called_once_with(**kwargs)
        self.task_repository.delete_by_owner_id.assert_called_once_with(self.target.id)
        self.reminder_repository.delete_by_user_id.assert_called_once_with(self.target.id)
        self.notification_repository.delete_by_user_id.assert_called_once_with(self.target.id)
        self.user_repository.soft_delete.assert_called_once()
        self.assertFalse(self.user_repository.delete.called)
        self.audit_log_repository.add.assert_called_once()
        self.session_revoker.revoke_all_sessions.assert_called_once_with(self.target.id)


class UnblockSoftDeletedUserTests(SimpleTestCase):

    def test_soft_deleted_user_cannot_be_unblocked(self):
        superadmin = domain_user(UserRole.SUPERADMIN)
        deleted = domain_user(is_active=False, deleted_at=timezone.now())
        user_repository = Mock()
        user_repository.get_by_id.return_value = deleted

        with self.assertRaisesMessage(ValueError, "A deleted user cannot be unblocked."):
            UnblockUserUseCase(user_repository, Mock(), Mock()).execute(
                superadmin, deleted.id,
            )

        user_repository.set_active.assert_not_called()


class UserRetirementWorkflowTests(TestCase):
    """End-to-end workflow against the real repositories and database."""

    def setUp(self):
        self.superadmin = User.objects.create_user(
            email="super@example.com", password="pw12345678",
            name="Super", role=User.Role.SUPERADMIN,
        )
        self.target = User.objects.create_user(
            email="target@example.com", password="pw12345678",
            name="Target", role=User.Role.ADMIN,
        )
        self.replacement = User.objects.create_user(
            email="replacement@example.com", password="pw12345678",
            name="Replacement", role=User.Role.ADMIN,
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="pw12345678",
            name="Other", role=User.Role.ADMIN,
        )
        self.now = timezone.now()

    # ---------- builders ----------

    def _lead(self, owner, name="Lead"):
        return DjangoLeadModel.objects.create(name=name, owner=owner)

    def _account(self, owner, created_by=None, name="Account"):
        created_by = created_by or owner
        return DjangoAccountModel.objects.create(
            account_owner=owner, account_name=name,
            created_by=created_by, modified_by=created_by,
            created_at=self.now, updated_at=self.now,
        )

    def _contact(self, owner, created_by=None, name="Contact"):
        created_by = created_by or owner
        return DjangoContactModel.objects.create(
            contact_owner=owner, name=name,
            created_by=created_by, modified_by=created_by,
            created_at=self.now, updated_at=self.now,
        )

    def _task(self, owner, subject="Task"):
        return DjangoTaskModel.objects.create(
            subject=subject, owner=owner, created_by=owner,
        )

    def _meeting(self, host, created_by=None, title="Meeting"):
        return DjangoMeetingModel.objects.create(
            title=title, host=host, created_by=created_by or host,
            start_at=self.now, end_at=self.now + timedelta(hours=1),
        )

    def _reminder(self, user, subject="Reminder"):
        return DjangoReminderModel.objects.create(
            subject=subject, remind_at=self.now + timedelta(days=1), user=user,
        )

    def _notification(self, user, title="Notification"):
        return DjangoNotificationModel.objects.create(
            notification_type="REMINDER", title=title, message="m", user=user,
            scheduled_for=self.now, expires_at=self.now + timedelta(days=1),
        )

    def _retire(self, replacement=None):
        get_delete_user_use_case().execute(
            current_user=DjangoUserRepository().get_by_id(self.superadmin.id),
            user_id=self.target.id,
            replacement_user_id=(replacement or self.replacement).id,
        )

    # ---------- tests ----------

    def test_successful_retirement(self):
        leads = [self._lead(self.target, "L1"), self._lead(self.target, "L2")]
        account = self._account(self.target, created_by=self.target)
        contacts = [self._contact(self.target, name="C1"), self._contact(self.target, name="C2")]
        tasks = [self._task(self.target, "T1"), self._task(self.target, "T2")]
        meetings = [self._meeting(self.target, title="M1"), self._meeting(self.target, title="M2")]
        reminders = [self._reminder(self.target), self._reminder(self.target)]
        notifications = [self._notification(self.target) for _ in range(3)]
        DjangoTimelineRepository().record(
            event_type="LEAD_CREATED", actor_id=self.target.id,
            message="created", metadata={}, targets=[("LEAD", leads[0].id)],
        )

        # Data of other users must be untouched.
        other_task = self._task(self.other, "Other task")
        other_reminder = self._reminder(self.other)
        other_notification = self._notification(self.other)
        other_lead = self._lead(self.other, "Other lead")

        self._retire()

        target = User.objects.get(id=self.target.id)
        self.assertIsNotNone(target.deleted_at)
        self.assertFalse(target.is_active)

        for lead in leads:
            lead.refresh_from_db()
            self.assertEqual(lead.owner_id, self.replacement.id)
        for contact in contacts:
            contact.refresh_from_db()
            self.assertEqual(contact.contact_owner_id, self.replacement.id)
            self.assertEqual(contact.created_by_id, self.target.id)
            self.assertEqual(contact.modified_by_id, self.target.id)
        account.refresh_from_db()
        self.assertEqual(account.account_owner_id, self.replacement.id)
        self.assertEqual(account.created_by_id, self.target.id)
        self.assertEqual(account.modified_by_id, self.target.id)
        for meeting in meetings:
            meeting.refresh_from_db()
            self.assertEqual(meeting.host_id, self.replacement.id)
            self.assertEqual(meeting.created_by_id, self.target.id)

        self.assertFalse(DjangoTaskModel.objects.filter(owner_id=self.target.id).exists())
        self.assertFalse(DjangoReminderModel.objects.filter(user_id=self.target.id).exists())
        self.assertFalse(DjangoNotificationModel.objects.filter(user_id=self.target.id).exists())

        event = TimelineEvent.objects.get(event_type="LEAD_CREATED")
        self.assertEqual(event.actor_id, self.target.id)
        self.assertFalse(event.is_deleted)

        self.assertTrue(DjangoTaskModel.objects.filter(id=other_task.id).exists())
        self.assertTrue(DjangoReminderModel.objects.filter(id=other_reminder.id).exists())
        self.assertTrue(DjangoNotificationModel.objects.filter(id=other_notification.id).exists())
        other_lead.refresh_from_db()
        self.assertEqual(other_lead.owner_id, self.other.id)

    def test_rollback_when_meeting_transfer_fails(self):
        lead = self._lead(self.target)
        contact = self._contact(self.target)
        account = self._account(self.target)
        task = self._task(self.target)
        meeting = self._meeting(self.target)
        reminder = self._reminder(self.target)
        notification = self._notification(self.target)

        with patch(
            "src.modules.meetings.infrastructure.persistence."
            "django_meeting_repository.DjangoMeetingRepository.transfer_host",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                self._retire()

        target = User.objects.get(id=self.target.id)
        self.assertIsNone(target.deleted_at)
        self.assertTrue(target.is_active)
        lead.refresh_from_db()
        contact.refresh_from_db()
        account.refresh_from_db()
        meeting.refresh_from_db()
        self.assertEqual(lead.owner_id, self.target.id)
        self.assertEqual(contact.contact_owner_id, self.target.id)
        self.assertEqual(account.account_owner_id, self.target.id)
        self.assertEqual(meeting.host_id, self.target.id)
        self.assertTrue(DjangoTaskModel.objects.filter(id=task.id).exists())
        self.assertTrue(DjangoReminderModel.objects.filter(id=reminder.id).exists())
        self.assertTrue(DjangoNotificationModel.objects.filter(id=notification.id).exists())

    def test_rollback_when_final_soft_delete_fails(self):
        lead = self._lead(self.target)
        task = self._task(self.target)
        reminder = self._reminder(self.target)
        notification = self._notification(self.target)

        with patch.object(
            DjangoUserRepository, "soft_delete", side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                self._retire()

        lead.refresh_from_db()
        self.assertEqual(lead.owner_id, self.target.id)
        self.assertTrue(DjangoTaskModel.objects.filter(id=task.id).exists())
        self.assertTrue(DjangoReminderModel.objects.filter(id=reminder.id).exists())
        self.assertTrue(DjangoNotificationModel.objects.filter(id=notification.id).exists())
        self.assertIsNone(User.objects.get(id=self.target.id).deleted_at)

    def test_user_without_relationships_is_soft_deleted(self):
        self._retire()

        target = User.objects.get(id=self.target.id)
        self.assertIsNotNone(target.deleted_at)
        self.assertFalse(target.is_active)

    def test_partial_relationships(self):
        contacts = [self._contact(self.target, name=f"C{i}") for i in range(5)]
        for i in range(2):
            self._task(self.target, f"T{i}")
        for i in range(3):
            self._reminder(self.target, f"R{i}")
        for i in range(4):
            self._notification(self.target, f"N{i}")

        self._retire()

        self.assertEqual(
            DjangoContactModel.objects.filter(contact_owner_id=self.replacement.id).count(), 5,
        )
        self.assertFalse(DjangoTaskModel.objects.filter(owner_id=self.target.id).exists())
        self.assertFalse(DjangoReminderModel.objects.filter(user_id=self.target.id).exists())
        self.assertFalse(DjangoNotificationModel.objects.filter(user_id=self.target.id).exists())
        self.assertIsNotNone(User.objects.get(id=self.target.id).deleted_at)

    def test_meeting_participation_is_preserved(self):
        meeting = self._meeting(self.other)
        DjangoMeetingParticipantModel.objects.create(
            meeting=meeting, participant_type="USER", user=self.target,
        )

        self._retire()

        meeting.refresh_from_db()
        self.assertEqual(meeting.host_id, self.other.id)
        self.assertTrue(
            DjangoMeetingParticipantModel.objects.filter(
                meeting=meeting, user_id=self.target.id,
            ).exists()
        )

    def test_soft_deleted_user_cannot_be_unblocked_or_authenticate(self):
        self._retire()

        with self.assertRaises(ValueError):
            UnblockUserUseCase(
                DjangoUserRepository(),
                DjangoUserAuditLogRepository(),
                DjangoTransactionManager(),
            ).execute(
                DjangoUserRepository().get_by_id(self.superadmin.id),
                self.target.id,
            )
        target = User.objects.get(id=self.target.id)
        self.assertFalse(target.is_active)
        self.assertFalse(self.client.login(email="target@example.com", password="pw12345678"))

    def test_soft_deleted_user_excluded_from_list_and_owner_choices(self):
        self._retire()
        repository = DjangoUserRepository()

        listed = repository.get_all(ListQuery(page=1, page_size=50)).results
        self.assertNotIn(self.target.id, [u.id for u in listed])
        self.assertNotIn(self.target.id, [u.id for u in repository.get_lead_owners()])
        # Still resolvable for historical references.
        self.assertIsNotNone(repository.get_by_id(self.target.id))
