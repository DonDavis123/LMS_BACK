import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meetings", "0005_backfill_meeting_company"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="djangomeetingmodel",
            name="meet_link",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="djangomeetingmodel",
            name="external_event_id",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="djangomeetingmodel",
            name="conference_provider",
            field=models.CharField(
                blank=True,
                choices=[("google_meet", "google_meet")],
                max_length=32,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="djangomeetingmodel",
            name="conference_status",
            field=models.CharField(
                choices=[("none", "none"), ("created", "created"), ("failed", "failed")],
                default="none",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="djangomeetingmodel",
            name="conference_error",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="djangomeetingmodel",
            name="calendar_owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
