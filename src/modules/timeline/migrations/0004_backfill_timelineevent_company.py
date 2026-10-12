from django.db import migrations

LEGACY_COMPANY_SLUG = "legacy"


def backfill_timeline_event_company(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Company = apps.get_model("companies", "DjangoCompanyModel")

    legacy_company = (
        Company._default_manager.using(db_alias)
        .filter(slug__iexact=LEGACY_COMPANY_SLUG)
        .first()
    )
    if legacy_company is None:
        return

    Model = apps.get_model("timeline", "TimelineEvent")
    (
        Model._default_manager.using(db_alias)
        .filter(company_id__isnull=True)
        .update(company_id=legacy_company.pk)
    )


class Migration(migrations.Migration):

    dependencies = [
        ("timeline", "0003_timelineevent_company"),
        ("companies", "0002_create_legacy_company"),
    ]

    operations = [
        migrations.RunPython(
            backfill_timeline_event_company,
            migrations.RunPython.noop,
        ),
    ]
