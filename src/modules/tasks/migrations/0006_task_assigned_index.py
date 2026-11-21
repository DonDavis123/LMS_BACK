from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0005_task_list_indexes"),
    ]

    operations = [
        # "Assigned to" filter / sort on the task list.
        migrations.AddIndex(
            model_name="djangotaskmodel",
            index=models.Index(
                fields=["company", "is_deleted", "assigned_to"],
                name="tasks_co_assigned_idx",
            ),
        ),
    ]
