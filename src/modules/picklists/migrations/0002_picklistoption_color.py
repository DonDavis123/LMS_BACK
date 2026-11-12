from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("picklists", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="djangopicklistoptionmodel",
            name="color",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]
