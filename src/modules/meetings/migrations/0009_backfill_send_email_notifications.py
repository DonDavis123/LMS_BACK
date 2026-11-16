from django.db import migrations


def enable_for_existing_meet_meetings(apps, schema_editor):
    """Meetings that already have a Meet link were emailed before this option
    existed, so keep emailing them."""
    Meeting = apps.get_model("meetings", "DjangoMeetingModel")
    Meeting.objects.filter(conference_status="created").update(
        send_email_notifications=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ("meetings", "0008_meeting_send_email_notifications"),
    ]

    operations = [
        migrations.RunPython(enable_for_existing_meet_meetings, migrations.RunPython.noop),
    ]
