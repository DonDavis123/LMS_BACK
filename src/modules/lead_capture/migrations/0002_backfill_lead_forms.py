import secrets

from django.db import migrations

BATCH_SIZE = 500
DEFAULT_TITLE = "Contact us"


def backfill_lead_forms(apps, schema_editor):
    """Give every company that has no lead form its default one.

    Blocked and unconfigured (no source, no owner), like a form created
    together with a new company. The token is generated here for every row
    on purpose: a model default would be evaluated once and shared.

    Idempotent: only companies without a form are touched, and a form that
    appears meanwhile is skipped by ``ignore_conflicts``.
    """
    db_alias = schema_editor.connection.alias
    Company = apps.get_model("companies", "DjangoCompanyModel")
    Form = apps.get_model("lead_capture", "DjangoLeadFormModel")

    company_ids = list(
        Company._default_manager.using(db_alias)
        .exclude(id__in=Form._default_manager.using(db_alias).values("company_id"))
        .values_list("id", flat=True)
    )

    for start in range(0, len(company_ids), BATCH_SIZE):
        Form._default_manager.using(db_alias).bulk_create(
            [
                Form(
                    company_id=company_id,
                    public_token=secrets.token_urlsafe(24),
                    title=DEFAULT_TITLE,
                    lead_source="",
                    assignment_mode="SINGLE_OWNER",
                    is_active=False,
                )
                for company_id in company_ids[start:start + BATCH_SIZE]
            ],
            ignore_conflicts=True,
        )


def remove_untouched_lead_forms(apps, schema_editor):
    """Undo: delete only forms nobody has configured or used.

    Anything an admin set up, or that has received submissions, is kept
    (the table itself is dropped only if 0001 is reversed too).
    """
    db_alias = schema_editor.connection.alias
    Form = apps.get_model("lead_capture", "DjangoLeadFormModel")
    (
        Form._default_manager.using(db_alias)
        .filter(
            is_active=False,
            lead_source="",
            single_owner__isnull=True,
            rotation_entries__isnull=True,
            submission_count=0,
        )
        .delete()
    )


class Migration(migrations.Migration):

    dependencies = [
        ("lead_capture", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_lead_forms, remove_untouched_lead_forms),
    ]
