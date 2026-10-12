from django.db import migrations

LEGACY_COMPANY_NAME = "Legacy Company"
LEGACY_COMPANY_SLUG = "legacy"
PLATFORM_ROLE = "PLATFORM_SUPERADMIN"

# Every business table whose rows belong to a company (model labels as they
# exist in the migration state at this point).
BUSINESS_MODELS = (
    ("leads", "DjangoLeadModel"),
    ("accounts", "DjangoAccountModel"),
    ("contacts", "DjangoContactModel"),
    ("tasks", "DjangoTaskModel"),
    ("meetings", "DjangoMeetingModel"),
    ("reminders", "DjangoReminderModel"),
    ("notifications", "DjangoNotificationModel"),
    ("timeline", "TimelineEvent"),
)


def _has_tenant_data(apps, db_alias) -> bool:
    User = apps.get_model("users", "User")
    if (
        User._default_manager.using(db_alias)
        .exclude(role=PLATFORM_ROLE)
        .exists()
    ):
        return True

    for app_label, model_name in BUSINESS_MODELS:
        model = apps.get_model(app_label, model_name)
        if model._default_manager.using(db_alias).exists():
            return True

    return False


def create_legacy_company(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Company = apps.get_model("companies", "DjangoCompanyModel")

    if (
        Company._default_manager.using(db_alias)
        .filter(slug__iexact=LEGACY_COMPANY_SLUG)
        .exists()
    ):
        return

    # A fresh, empty database must stay empty.
    if not _has_tenant_data(apps, db_alias):
        return

    Company._default_manager.using(db_alias).create(
        name=LEGACY_COMPANY_NAME,
        slug=LEGACY_COMPANY_SLUG,
        status="ACTIVE",
    )


class Migration(migrations.Migration):

    # The other apps' latest pre-company migrations are listed so their models
    # exist in the migration state used by the existence check above. None of
    # them depends on this migration, so the graph stays acyclic.
    dependencies = [
        ("companies", "0001_initial"),
        ("users", "0005_user_audit_log"),
        ("leads", "0004_alter_djangoleadmodel_company_name"),
        ("accounts", "0002_drop_unique_active_account_name"),
        ("contacts", "0003_djangocontactmodel_is_deleted"),
        ("tasks", "0001_initial"),
        ("meetings", "0003_djangomeetingmodel_reminder_at"),
        ("reminders", "0002_djangoremindermodel_is_enabled"),
        ("notifications", "0005_notification_dismissed_at"),
        ("timeline", "0002_soft_delete"),
    ]

    operations = [
        migrations.RunPython(
            create_legacy_company,
            migrations.RunPython.noop,
        ),
    ]
