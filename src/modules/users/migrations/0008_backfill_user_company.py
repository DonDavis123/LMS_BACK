from django.db import migrations

LEGACY_COMPANY_SLUG = "legacy"
PLATFORM_ROLE = "PLATFORM_SUPERADMIN"


def backfill_user_company(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Company = apps.get_model("companies", "DjangoCompanyModel")

    legacy_company = (
        Company._default_manager.using(db_alias)
        .filter(slug__iexact=LEGACY_COMPANY_SLUG)
        .first()
    )
    if legacy_company is None:
        return

    # Platform superadmins belong to the platform, never to a company.
    User = apps.get_model("users", "User")
    (
        User._default_manager.using(db_alias)
        .filter(company_id__isnull=True)
        .exclude(role=PLATFORM_ROLE)
        .update(company_id=legacy_company.pk)
    )

    AuditLog = apps.get_model("users", "DjangoUserAuditLogModel")
    (
        AuditLog._default_manager.using(db_alias)
        .filter(company_id__isnull=True)
        .update(company_id=legacy_company.pk)
    )


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0007_user_email_lower_unique"),
        ("companies", "0002_create_legacy_company"),
    ]

    operations = [
        migrations.RunPython(
            backfill_user_company,
            migrations.RunPython.noop,
        ),
    ]
