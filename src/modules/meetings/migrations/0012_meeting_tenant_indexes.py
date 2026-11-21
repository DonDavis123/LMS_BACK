from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meetings", "0011_meeting_list_indexes"),
    ]

    operations = [
        # Reminder / conference jobs: this company's open meetings that have
        # not ended yet.
        migrations.AddIndex(
            model_name="djangomeetingmodel",
            index=models.Index(
                fields=["company", "is_deleted", "end_at"],
                name="meetings_co_end_idx",
            ),
        ),
        # "Host" sort on the meeting list and the host-ownership count.
        migrations.AddIndex(
            model_name="djangomeetingmodel",
            index=models.Index(
                fields=["company", "is_deleted", "host"],
                name="meetings_co_host_idx",
            ),
        ),
    ]
