import json
import logging
from html import escape
from urllib import request

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from src.modules.authentication.infrastructure.email.http_email_service import (
    HttpEmailService,
)
from src.modules.meetings.application.interfaces.meeting_reminder_notifier import (
    MeetingReminder,
    MeetingReminderNotifier,
)

logger = logging.getLogger(__name__)


class MeetingReminderEmailer(MeetingReminderNotifier):
    """Sends the reminder through the same mail setup as password resets
    (HTTP relay when EMAIL_PROVIDER is ``http``, otherwise Django SMTP)."""

    def send(self, recipient_email: str, reminder: MeetingReminder) -> None:
        subject = f"Reminder: {reminder.title} starts soon"
        text, html = self._render(reminder)

        if settings.EMAIL_PROVIDER == "http":
            self._send_http(recipient_email, subject, text, html)
        else:
            message = EmailMultiAlternatives(
                subject=subject,
                body=text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],  # one email per person: no address leaks
            )
            message.attach_alternative(html, "text/html")
            message.send(fail_silently=False)

    @staticmethod
    def _render(reminder: MeetingReminder) -> tuple[str, str]:
        start = timezone.localtime(reminder.start_at)
        end = timezone.localtime(reminder.end_at)
        when = (
            f"{start.strftime('%a, %d %b %Y, %I:%M %p')} to "
            f"{end.strftime('%I:%M %p')} {start.tzname() or ''}"
        ).strip()

        lines = [f"Your meeting \"{reminder.title}\" is about to start.", "", f"When: {when}"]
        if reminder.host_name:
            lines.append(f"Host: {reminder.host_name}")
        if reminder.location:
            lines.append(f"Location: {reminder.location}")
        lines += ["", f"Join with Google Meet: {reminder.meet_link}"]
        text = "\n".join(lines)

        rows = [f"<p>Your meeting <strong>{escape(reminder.title)}</strong> is about to start.</p>",
                f"<p><strong>When:</strong> {escape(when)}</p>"]
        if reminder.host_name:
            rows.append(f"<p><strong>Host:</strong> {escape(reminder.host_name)}</p>")
        if reminder.location:
            rows.append(f"<p><strong>Location:</strong> {escape(reminder.location)}</p>")
        link = escape(reminder.meet_link, quote=True)
        rows.append(f'<p><a href="{link}">Join with Google Meet</a></p>')
        rows.append(f"<p style=\"color:#666;font-size:12px\">{link}</p>")
        return text, "".join(rows)

    @staticmethod
    def _send_http(to: str, subject: str, text: str, html: str) -> None:
        endpoint = HttpEmailService._get_endpoint()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "lms-backend/1.0",
        }
        if settings.EMAIL_HTTP_TOKEN:
            headers["Authorization"] = f"Bearer {settings.EMAIL_HTTP_TOKEN}"

        http_request = request.Request(
            endpoint,
            data=json.dumps(
                {"to": to, "subject": subject, "text": text, "html": html}
            ).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with request.urlopen(http_request, timeout=settings.EMAIL_TIMEOUT) as response:
            body = response.read().decode("utf-8", errors="replace")
            final_url = response.geturl()

        HttpEmailService._raise_if_relay_returned_a_web_page(body, final_url)
        HttpEmailService._raise_if_relay_reported_failure(body)
