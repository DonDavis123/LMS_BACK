from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.companies.infrastructure.persistence.django_company_model import (
    DjangoCompanyModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.meetings.infrastructure.persistence.models import (
    DjangoMeetingModel,
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

# The state in which every company column exists but no data migration has
# run yet (companies 0002 and the per-app backfills are not applied).
BEFORE_BACKFILL = [
    ("companies", "0001_initial"),
    ("users", "0007_user_email_lower_unique"),
    ("accounts", "0003_djangoaccountmodel_company"),
    ("contacts", "0004_djangocontactmodel_company"),
    ("leads", "0005_djangoleadmodel_company"),
    ("meetings", "0004_djangomeetingmodel_company"),
    ("notifications", "0006_djangonotificationmodel_company"),
    ("reminders", "0003_djangoremindermodel_company"),
    ("tasks", "0002_djangotaskmodel_company"),
    ("timeline", "0003_timelineevent_company"),
]

BUSINESS_MODELS = (
    DjangoLeadModel,
    DjangoAccountModel,
    DjangoContactModel,
    DjangoTaskModel,
    DjangoMeetingModel,
    DjangoReminderModel,
    DjangoNotificationModel,
    TimelineEvent,
)


def run_audit_command():
    out = StringIO()
    try:
        call_command("audit_tenant_data", stdout=out)
    except SystemExit as exc:
        return exc.code, out.getvalue()
    return 0, out.getvalue()


class TenantBackfillMigrationTests(TransactionTestCase):

    def setUp(self):
        # Whatever happens, leave the database fully migrated for other tests.
        self.addCleanup(self.migrate_to_latest)
        self.old_apps = self.migrate_to(BEFORE_BACKFILL)

    @staticmethod
    def migrate_to(targets):
        executor = MigrationExecutor(connection)
        executor.migrate(targets)
        executor.loader.build_graph()
        return executor.loader.project_state(targets).apps

    @staticmethod
    def migrate_to_latest():
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    # -- rows created through the historical (pre-backfill) models ---------

    def create_rows_without_company(self, suffix="", platform_user=True):
        apps = self.old_apps
        OldUser = apps.get_model("users", "User")
        OldAuditLog = apps.get_model("users", "DjangoUserAuditLogModel")
        OldLead = apps.get_model("leads", "DjangoLeadModel")
        OldAccount = apps.get_model("accounts", "DjangoAccountModel")
        OldContact = apps.get_model("contacts", "DjangoContactModel")
        OldTask = apps.get_model("tasks", "DjangoTaskModel")
        OldMeeting = apps.get_model("meetings", "DjangoMeetingModel")
        OldReminder = apps.get_model("reminders", "DjangoReminderModel")
        OldNotification = apps.get_model("notifications", "DjangoNotificationModel")
        OldTimelineEvent = apps.get_model("timeline", "TimelineEvent")

        now = timezone.now()
        user = OldUser.objects.create(
            email=f"admin{suffix}@example.com",
            password="not-a-real-hash",
            name="Admin",
            role="ADMIN",
        )
        if platform_user:
            OldUser.objects.create(
                email=f"platform{suffix}@example.com",
                password="not-a-real-hash",
                name="Platform",
                role="PLATFORM_SUPERADMIN",
            )
        lead = OldLead.objects.create(name="Lead", owner=user)
        account = OldAccount.objects.create(
            account_owner=user,
            account_name="Account",
            created_by=user,
            created_at=now,
            modified_by=user,
            updated_at=now,
        )
        contact = OldContact.objects.create(
            account=account,
            contact_owner=user,
            name="Contact",
            created_by=user,
            created_at=now,
            modified_by=user,
            updated_at=now,
        )
        task = OldTask.objects.create(
            subject="Task",
            owner=user,
            created_by=user,
            lead=lead,
            contact=contact,
            account=account,
        )
        meeting = OldMeeting.objects.create(
            title="Meeting",
            start_at=now,
            end_at=now + timedelta(hours=1),
            host=user,
            created_by=user,
        )
        OldReminder.objects.create(
            subject="Reminder",
            remind_at=now,
            user=user,
            task=task,
        )
        OldNotification.objects.create(
            notification_type="MEETING_TODAY",
            title="Meeting",
            message="Meeting today",
            user=user,
            meeting=meeting,
            scheduled_for=now,
            expires_at=now + timedelta(days=1),
        )
        OldTimelineEvent.objects.create(
            event_type="LEAD_CREATED",
            actor=user,
            message="Lead created",
        )
        OldAuditLog.objects.create(
            action="USER_CREATED",
            actor_id=user.id,
            actor_email=user.email,
            target_user_id=user.id,
            target_email=user.email,
            created_at=now,
        )

    # -- tests --------------------------------------------------------------

    def test_backfill_assigns_every_row_to_the_legacy_company(self):
        self.create_rows_without_company()

        self.migrate_to_latest()

        legacy = DjangoCompanyModel.objects.get(slug="legacy")
        self.assertEqual(legacy.name, "Legacy Company")
        self.assertEqual(legacy.status, DjangoCompanyModel.Status.ACTIVE)
        self.assertEqual(DjangoCompanyModel.objects.count(), 1)

        admin = User.objects.get(email="admin@example.com")
        self.assertEqual(admin.company_id, legacy.id)

        for model in BUSINESS_MODELS:
            with self.subTest(model=model.__name__):
                self.assertEqual(model._default_manager.count(), 1)
                self.assertEqual(
                    model._default_manager.filter(company_id=legacy.id).count(),
                    1,
                )
                self.assertFalse(
                    model._default_manager.filter(company__isnull=True).exists()
                )

        self.assertEqual(
            DjangoUserAuditLogModel.objects.filter(company_id=legacy.id).count(),
            1,
        )

        code, output = run_audit_command()
        self.assertEqual(code, 0, output)

    def test_platform_superadmin_is_not_assigned_to_a_company(self):
        self.create_rows_without_company()

        self.migrate_to_latest()

        platform = User.objects.get(email="platform@example.com")
        self.assertEqual(platform.role, User.Role.PLATFORM_SUPERADMIN)
        self.assertIsNone(platform.company_id)

    def test_backfill_is_rerunnable(self):
        self.create_rows_without_company()
        self.migrate_to_latest()
        legacy = DjangoCompanyModel.objects.get(slug="legacy")

        # Unapply the data migrations (their reverse is a no-op), add rows
        # that again have no company, and apply them a second time.
        self.old_apps = self.migrate_to(BEFORE_BACKFILL)
        self.create_rows_without_company(suffix="-2", platform_user=False)
        self.migrate_to_latest()

        self.assertEqual(DjangoCompanyModel.objects.count(), 1)
        self.assertEqual(DjangoCompanyModel.objects.get(slug="legacy").id, legacy.id)
        for model in BUSINESS_MODELS:
            with self.subTest(model=model.__name__):
                self.assertEqual(model._default_manager.count(), 2)
                self.assertFalse(
                    model._default_manager.filter(company__isnull=True).exists()
                )
        self.assertEqual(User.objects.filter(company_id=legacy.id).count(), 2)

        code, output = run_audit_command()
        self.assertEqual(code, 0, output)

    def test_empty_database_gets_no_legacy_company(self):
        self.migrate_to_latest()

        self.assertFalse(DjangoCompanyModel.objects.exists())

        code, output = run_audit_command()
        self.assertEqual(code, 0, output)

    def test_database_with_only_a_platform_superadmin_gets_no_legacy_company(self):
        self.old_apps.get_model("users", "User").objects.create(
            email="platform@example.com",
            password="not-a-real-hash",
            name="Platform",
            role="PLATFORM_SUPERADMIN",
        )

        self.migrate_to_latest()

        self.assertFalse(DjangoCompanyModel.objects.exists())
        self.assertIsNone(
            User.objects.get(email="platform@example.com").company_id
        )

    def test_existing_legacy_company_is_reused(self):
        existing = self.old_apps.get_model("companies", "DjangoCompanyModel").objects.create(
            name="Existing",
            slug="Legacy",
        )
        self.create_rows_without_company()

        self.migrate_to_latest()

        self.assertEqual(DjangoCompanyModel.objects.count(), 1)
        self.assertEqual(
            User.objects.get(email="admin@example.com").company_id,
            existing.id,
        )
