from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.companies.infrastructure.persistence.django_company_model import (
    DjangoCompanyModel,
)
from src.modules.companies.infrastructure.persistence.tenant_data_audit import (
    run_tenant_data_audit,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.meetings.domain.enums.meeting_participant_type import (
    MeetingParticipantType,
)
from src.modules.meetings.domain.enums.meeting_related_record_type import (
    MeetingRelatedRecordType,
)
from src.modules.meetings.infrastructure.persistence.models import (
    DjangoMeetingModel,
    DjangoMeetingParticipantModel,
    DjangoMeetingRelatedRecordModel,
)
from src.modules.notifications.domain.enums.notification_type import (
    NotificationType,
)
from src.modules.notifications.infrastructure.persistence.models import (
    DjangoNotificationModel,
)
from src.modules.reminders.infrastructure.persistence.models import (
    DjangoReminderModel,
)
from src.modules.tasks.infrastructure.persistence.models import DjangoTaskModel
from src.modules.timeline.infrastructure.persistence.models import TimelineEvent
from src.modules.users.infrastructure.persistence.models import User
from src.modules.users.infrastructure.persistence.user_audit_log_model import (
    DjangoUserAuditLogModel,
)


def run_audit_command():
    """Return (exit code, printed output) of audit_tenant_data."""
    out = StringIO()
    try:
        call_command("audit_tenant_data", stdout=out)
    except SystemExit as exc:
        return exc.code, out.getvalue()
    return 0, out.getvalue()


class AuditTenantDataTests(TestCase):

    def setUp(self):
        self.now = timezone.now()
        self.company = DjangoCompanyModel.objects.create(name="Acme", slug="acme")
        self.other_company = DjangoCompanyModel.objects.create(
            name="Globex",
            slug="globex",
        )
        self.user = self.make_user("owner@example.com", self.company)

    # -- builders -----------------------------------------------------------

    def make_user(self, email, company, role=User.Role.ADMIN):
        return User.objects.create_user(
            email=email,
            password="password-123",
            name=email.split("@")[0],
            role=role,
            company=company,
        )

    def make_lead(self, owner, company, name="Lead"):
        return DjangoLeadModel.objects.create(name=name, owner=owner, company=company)

    def make_account(self, owner, company, name="Account"):
        return DjangoAccountModel.objects.create(
            account_owner=owner,
            account_name=name,
            created_by=owner,
            created_at=self.now,
            modified_by=owner,
            updated_at=self.now,
            company=company,
        )

    def make_contact(self, owner, company, account=None, name="Contact"):
        return DjangoContactModel.objects.create(
            account=account,
            contact_owner=owner,
            name=name,
            created_by=owner,
            created_at=self.now,
            modified_by=owner,
            updated_at=self.now,
            company=company,
        )

    def make_task(self, owner, company, **relations):
        return DjangoTaskModel.objects.create(
            subject="Task",
            owner=owner,
            created_by=owner,
            company=company,
            **relations,
        )

    def make_meeting(self, host, company):
        return DjangoMeetingModel.objects.create(
            title="Meeting",
            start_at=self.now,
            end_at=self.now + timedelta(hours=1),
            host=host,
            created_by=host,
            company=company,
        )

    def build_consistent_dataset(self):
        company, user = self.company, self.user

        lead = self.make_lead(user, company)
        account = self.make_account(user, company)
        contact = self.make_contact(user, company, account=account)
        task = self.make_task(
            user,
            company,
            lead=lead,
            contact=contact,
            account=account,
        )
        meeting = self.make_meeting(user, company)

        DjangoMeetingParticipantModel.objects.create(
            meeting=meeting,
            participant_type=MeetingParticipantType.USER.value,
            user=user,
        )
        DjangoMeetingParticipantModel.objects.create(
            meeting=meeting,
            participant_type=MeetingParticipantType.LEAD.value,
            lead=lead,
        )
        DjangoMeetingParticipantModel.objects.create(
            meeting=meeting,
            participant_type=MeetingParticipantType.CONTACT.value,
            contact=contact,
        )
        DjangoMeetingRelatedRecordModel.objects.create(
            meeting=meeting,
            record_type=MeetingRelatedRecordType.LEAD.value,
            lead=lead,
        )
        DjangoMeetingRelatedRecordModel.objects.create(
            meeting=meeting,
            record_type=MeetingRelatedRecordType.CONTACT.value,
            contact=contact,
        )

        task_reminder = DjangoReminderModel.objects.create(
            subject="Task reminder",
            remind_at=self.now,
            user=user,
            task=task,
            company=company,
        )
        DjangoReminderModel.objects.create(
            subject="Meeting reminder",
            remind_at=self.now,
            user=user,
            meeting=meeting,
            company=company,
        )
        DjangoNotificationModel.objects.create(
            notification_type=NotificationType.REMINDER.value,
            title="Reminder",
            message="Reminder due",
            user=user,
            task=task,
            reminder=task_reminder,
            scheduled_for=self.now,
            expires_at=self.now + timedelta(days=1),
            company=company,
        )
        DjangoNotificationModel.objects.create(
            notification_type=NotificationType.MEETING_TODAY.value,
            title="Meeting",
            message="Meeting today",
            user=user,
            meeting=meeting,
            scheduled_for=self.now,
            expires_at=self.now + timedelta(days=1),
            company=company,
        )
        TimelineEvent.objects.create(
            event_type="LEAD_CREATED",
            actor=user,
            message="Lead created",
            company=company,
        )
        DjangoUserAuditLogModel.objects.create(
            action="USER_CREATED",
            actor_id=user.id,
            actor_email=user.email,
            target_user_id=user.id,
            target_email=user.email,
            created_at=self.now,
            company_id=company.id,
        )
        # Platform superadmins belong to no company.
        self.make_user(
            "platform@example.com",
            None,
            role=User.Role.PLATFORM_SUPERADMIN,
        )

        return {"lead": lead, "account": account, "contact": contact, "task": task}

    @staticmethod
    def counts(checks):
        return {check.name: check.count for check in checks}

    # -- tests --------------------------------------------------------------

    def test_empty_database_exits_zero(self):
        User.objects.all().delete()

        code, output = run_audit_command()

        self.assertEqual(code, 0, output)
        self.assertIn("OK", output)

    def test_consistent_data_exits_zero(self):
        self.build_consistent_dataset()

        code, output = run_audit_command()

        self.assertEqual(code, 0, output)
        self.assertTrue(all(count == 0 for count in self.counts(run_tenant_data_audit()).values()))

    def test_null_company_exits_one(self):
        self.build_consistent_dataset()
        DjangoLeadModel.objects.update(company=None)

        code, output = run_audit_command()
        counts = self.counts(run_tenant_data_audit())

        self.assertEqual(code, 1, output)
        self.assertEqual(counts["leads"], 1)
        self.assertIn("FAILED", output)
        self.assertEqual(
            {name for name, count in counts.items() if count},
            {"leads"},
        )

    def test_user_without_company_is_reported(self):
        self.make_user("nocompany@example.com", None)

        code, _ = run_audit_command()
        counts = self.counts(run_tenant_data_audit())

        self.assertEqual(code, 1)
        self.assertEqual(counts["non-platform users"], 1)
        self.assertEqual(counts["non-platform users without a company"], 1)

    def test_platform_superadmin_with_company_is_reported(self):
        self.make_user(
            "platform@example.com",
            self.company,
            role=User.Role.PLATFORM_SUPERADMIN,
        )

        code, _ = run_audit_command()
        counts = self.counts(run_tenant_data_audit())

        self.assertEqual(code, 1)
        self.assertEqual(counts["platform superadmins with a company"], 1)

    def test_platform_superadmin_without_company_is_fine(self):
        self.make_user(
            "platform@example.com",
            None,
            role=User.Role.PLATFORM_SUPERADMIN,
        )

        code, output = run_audit_command()

        self.assertEqual(code, 0, output)

    def test_task_with_lead_from_another_company_exits_one(self):
        foreign_owner = self.make_user("foreign@example.com", self.other_company)
        foreign_lead = self.make_lead(foreign_owner, self.other_company)
        self.make_task(self.user, self.company, lead=foreign_lead)

        code, output = run_audit_command()
        counts = self.counts(run_tenant_data_audit())

        self.assertEqual(code, 1, output)
        self.assertEqual(counts["task vs lead"], 1)
        self.assertEqual(
            {name for name, count in counts.items() if count},
            {"task vs lead"},
        )

    def test_lead_owned_by_user_of_another_company_is_reported(self):
        foreign_owner = self.make_user("foreign@example.com", self.other_company)
        self.make_lead(foreign_owner, self.company)

        counts = self.counts(run_tenant_data_audit())

        self.assertEqual(counts["lead vs owner"], 1)

    def test_meeting_participant_from_another_company_is_reported(self):
        foreign_owner = self.make_user("foreign@example.com", self.other_company)
        foreign_lead = self.make_lead(foreign_owner, self.other_company)
        foreign_contact = self.make_contact(foreign_owner, self.other_company)
        meeting = self.make_meeting(self.user, self.company)
        DjangoMeetingParticipantModel.objects.create(
            meeting=meeting,
            participant_type=MeetingParticipantType.USER.value,
            user=foreign_owner,
        )
        DjangoMeetingParticipantModel.objects.create(
            meeting=meeting,
            participant_type=MeetingParticipantType.LEAD.value,
            lead=foreign_lead,
        )
        DjangoMeetingRelatedRecordModel.objects.create(
            meeting=meeting,
            record_type=MeetingRelatedRecordType.CONTACT.value,
            contact=foreign_contact,
        )

        counts = self.counts(run_tenant_data_audit())

        self.assertEqual(counts["meeting participant (user) vs meeting"], 1)
        self.assertEqual(counts["meeting participant (lead) vs meeting"], 1)
        self.assertEqual(counts["meeting related contact vs meeting"], 1)
        self.assertEqual(counts["meeting participant (contact) vs meeting"], 0)

    def test_reminder_and_notification_mismatches_are_reported(self):
        foreign_owner = self.make_user("foreign@example.com", self.other_company)
        task = self.make_task(self.user, self.company)
        reminder = DjangoReminderModel.objects.create(
            subject="Reminder",
            remind_at=self.now,
            user=foreign_owner,
            task=task,
            company=self.company,
        )
        DjangoNotificationModel.objects.create(
            notification_type=NotificationType.REMINDER.value,
            title="Reminder",
            message="Reminder due",
            user=self.user,
            reminder=reminder,
            scheduled_for=self.now,
            expires_at=self.now + timedelta(days=1),
            company=self.other_company,
        )

        counts = self.counts(run_tenant_data_audit())

        self.assertEqual(counts["reminder vs user"], 1)
        self.assertEqual(counts["notification vs user"], 1)
        self.assertEqual(counts["notification vs reminder"], 1)
        self.assertEqual(counts["reminder vs task"], 0)

    def test_timeline_event_by_actor_of_another_company_is_reported(self):
        TimelineEvent.objects.create(
            event_type="LEAD_CREATED",
            actor=self.user,
            message="Lead created",
            company=self.other_company,
        )

        counts = self.counts(run_tenant_data_audit())

        self.assertEqual(counts["timeline event vs actor"], 1)
