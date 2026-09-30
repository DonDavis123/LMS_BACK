from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_alter_user_role"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("SUPERADMIN", "Superadmin"),
                    ("ADMIN", "Admin"),
                    ("SALES_MANAGER", "Sales Manager"),
                    ("SALES_EXECUTIVE", "Sales Executive"),
                ],
                default="ADMIN",
                max_length=30,
            ),
        ),
    ]
