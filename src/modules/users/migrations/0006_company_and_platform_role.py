import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0001_initial"),
        ("users", "0005_user_audit_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="company",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="companies.djangocompanymodel",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("SUPERADMIN", "Superadmin"),
                    ("ADMIN", "Admin"),
                    ("SALES_MANAGER", "Sales Manager"),
                    ("SALES_EXECUTIVE", "Sales Executive"),
                    ("PLATFORM_SUPERADMIN", "Platform Superadmin"),
                ],
                default="ADMIN",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="djangouserauditlogmodel",
            name="company_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
