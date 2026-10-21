import django.db.models.deletion
import src.modules.calls.domain.enums.call_entry_method
import src.modules.calls.domain.enums.call_type
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0005_alter_account_ownership"),
        ("companies", "0003_platform_audit_log"),
        ("contacts", "0005_backfill_contact_company"),
        ("leads", "0009_alter_lead_option_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DjangoCallModel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("call_type", models.CharField(choices=[("Outbound", "Outbound"), ("Inbound", "Inbound")], default=src.modules.calls.domain.enums.call_type.CallType["OUTBOUND"], max_length=100)),
                ("outcome", models.CharField(choices=[("Connected", "Connected"), ("Not Attended", "Not Attended"), ("Busy", "Busy"), ("Voicemail", "Voicemail"), ("Wrong Number", "Wrong Number"), ("Callback Requested", "Callback Requested")], max_length=100)),
                ("entry_method", models.CharField(choices=[("MANUAL", "MANUAL"), ("TIMER", "TIMER")], default=src.modules.calls.domain.enums.call_entry_method.CallEntryMethod["MANUAL"], max_length=100)),
                ("call_start_time", models.DateTimeField()),
                ("duration_seconds", models.PositiveIntegerField(default=0)),
                ("description", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="calls", to="accounts.djangoaccountmodel")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="companies.djangocompanymodel")),
                ("contact", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="calls", to="contacts.djangocontactmodel")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_calls", to=settings.AUTH_USER_MODEL)),
                ("lead", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="calls", to="leads.djangoleadmodel")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="owned_calls", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "calls",
                "indexes": [
                    models.Index(fields=["company", "lead", "-call_start_time"], name="calls_co_lead_start_idx"),
                    models.Index(fields=["company", "contact", "-call_start_time"], name="calls_co_contact_start_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(models.Q(("contact__isnull", True), ("lead__isnull", False)), models.Q(("contact__isnull", False), ("lead__isnull", True)), _connector="OR"), name="call_exactly_one_of_lead_contact"),
                    models.CheckConstraint(condition=models.Q(("account__isnull", True), ("contact__isnull", False), _connector="OR"), name="call_account_only_with_contact"),
                ],
            },
        ),
    ]
