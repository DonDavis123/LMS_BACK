from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0004_djangotaskmodel_assigned_to"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="djangotaskmodel",
            index=models.Index(
                fields=["company", "is_deleted", "created_at"],
                name="tasks_co_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangotaskmodel",
            index=models.Index(
                fields=["company", "is_deleted", "status"],
                name="tasks_co_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangotaskmodel",
            index=models.Index(
                fields=["company", "is_deleted", "due_date"],
                name="tasks_co_due_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangotaskmodel",
            index=models.Index(
                fields=["company", "is_deleted", "owner"],
                name="tasks_co_owner_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangotaskmodel",
            index=models.Index(
                fields=["contact", "is_deleted", "due_date", "created_at"],
                name="tasks_contact_next_idx",
            ),
        ),
    ]
