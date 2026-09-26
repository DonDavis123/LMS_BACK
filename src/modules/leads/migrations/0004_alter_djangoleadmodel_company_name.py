from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0003_djangoleadmodel_is_converted_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="djangoleadmodel",
            name="company_name",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
            ),
        ),
    ]
