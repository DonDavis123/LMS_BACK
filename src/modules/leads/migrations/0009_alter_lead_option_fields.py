from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0008_alter_djangoleadmodel_lead_source"),
    ]

    operations = [
        migrations.AlterField(
            model_name="djangoleadmodel",
            name="lead_source",
            field=models.CharField(default="None", max_length=100),
        ),
        migrations.AlterField(
            model_name="djangoleadmodel",
            name="lead_status",
            field=models.CharField(default="None", max_length=100),
        ),
        migrations.AlterField(
            model_name="djangoleadmodel",
            name="industry",
            field=models.CharField(default="None", max_length=150),
        ),
        migrations.AlterField(
            model_name="djangoleadmodel",
            name="rating",
            field=models.CharField(default="None", max_length=100),
        ),
    ]
