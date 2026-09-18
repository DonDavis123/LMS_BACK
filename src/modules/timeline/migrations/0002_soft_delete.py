from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("timeline", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="timelineevent",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="timelineeventtarget",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
    ]
