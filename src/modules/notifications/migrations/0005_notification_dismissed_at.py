from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0004_notification_event_uniques"),
    ]

    operations = [
        migrations.AddField(
            model_name="djangonotificationmodel",
            name="dismissed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
