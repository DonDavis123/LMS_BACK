from django.db import migrations, models
from django.db.models import Count
from django.db.models.functions import Lower


def precheck_duplicate_emails(apps, schema_editor):
    """Fail early, with a readable message, if emails collide ignoring case."""
    db_alias = schema_editor.connection.alias
    User = apps.get_model("users", "User")

    duplicated = [
        row["email_lower"]
        for row in (
            User._default_manager.using(db_alias)
            .annotate(email_lower=Lower("email"))
            .values("email_lower")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .order_by("email_lower")
        )
    ]
    if not duplicated:
        return

    users = (
        User._default_manager.using(db_alias)
        .annotate(email_lower=Lower("email"))
        .filter(email_lower__in=duplicated)
        .order_by("email_lower", "created_at", "id")
        .values_list("email_lower", "id", "email")
    )
    grouped: dict[str, list[str]] = {}
    for email_lower, user_id, email in users:
        grouped.setdefault(email_lower, []).append(f"{user_id} ({email})")

    details = "\n".join(
        f"  {email_lower}: {', '.join(entries)}"
        for email_lower, entries in grouped.items()
    )
    raise RuntimeError(
        "Cannot add the case-insensitive unique constraint "
        "'user_email_lower_unique': these emails are duplicated when compared "
        "ignoring case. Merge, rename or remove the extra users, then run "
        "'python manage.py check_duplicate_emails' until it reports nothing "
        "and migrate again.\n" + details
    )


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_company_and_platform_role"),
    ]

    operations = [
        migrations.RunPython(
            precheck_duplicate_emails,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                Lower("email"),
                name="user_email_lower_unique",
            ),
        ),
    ]
