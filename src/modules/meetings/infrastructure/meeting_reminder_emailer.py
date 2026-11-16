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
    KIND_CANCELLATION,
    KIND_INVITATION,
    KIND_UPDATE,
    MeetingReminder,
    MeetingReminderNotifier,
)

logger = logging.getLogger(__name__)


class MeetingReminderEmailer(MeetingReminderNotifier):
    """Sends meeting emails (invitation, update, cancellation, reminder)
    through the same mail setup as password resets (HTTP relay when
    EMAIL_PROVIDER is ``http``, otherwise Django SMTP).

    Every email shows the meeting heading (title) and its description.
    """

    def send(self, recipient_email: str, reminder: MeetingReminder) -> None:
        subject = self._subject(reminder)
        text, html = self._render(reminder)

        if settings.EMAIL_PROVIDER == "http":
            self._send_http(recipient_email, subject, text, html)
        else:
            message = EmailMultiAlternatives(
                subject=subject,
                body=text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],  # one email per person: no address leaks
                # Replies go to the person who created the meeting.
                reply_to=[reminder.reply_to] if reminder.reply_to else None,
            )
            message.attach_alternative(html, "text/html")
            message.send(fail_silently=False)

    @staticmethod
    def _subject(reminder: MeetingReminder) -> str:
        title = reminder.title
        if reminder.kind == KIND_INVITATION:
            return f"Invitation: {title}"
        if reminder.kind == KIND_UPDATE:
            return f"Updated: {title}"
        if reminder.kind == KIND_CANCELLATION:
            return f"Cancelled: {title}"
        # Reminder: the creator's subject, else just the meeting heading.
        return (reminder.subject or "").strip() or title

    @staticmethod
    def _intro(reminder: MeetingReminder) -> str:
        if reminder.kind == KIND_INVITATION:
            return "You have been invited to a meeting."
        if reminder.kind == KIND_UPDATE:
            return "This meeting has been updated. The details below are current."
        if reminder.kind == KIND_CANCELLATION:
            return "This meeting has been cancelled."
        if reminder.sender_name:
            return f"Reminder from {reminder.sender_name}: your meeting is coming up."
        return "Your meeting is coming up."

    @staticmethod
    def _when(reminder: MeetingReminder) -> str:
        start = timezone.localtime(reminder.start_at)
        end = timezone.localtime(reminder.end_at)
        if reminder.is_all_day:
            return f"{start.strftime('%a, %d %b %Y')} (all day)"
        return (
            f"{start.strftime('%a, %d %b %Y, %I:%M %p')} to "
            f"{end.strftime('%I:%M %p')} {start.tzname() or ''}"
        ).strip()

    @classmethod
    def _render(cls, reminder: MeetingReminder) -> tuple[str, str]:
        intro = cls._intro(reminder)
        when = cls._when(reminder)
        description = (reminder.description or "").strip()
        cancelled = reminder.kind == KIND_CANCELLATION

        # ---- plain text
        lines = [reminder.title, "=" * min(len(reminder.title), 60), "", intro, ""]
        if description:
            lines += ["Description:", description, ""]
        lines.append(f"When: {when}")
        if reminder.host_name:
            lines.append(f"Host: {reminder.host_name}")
        if reminder.location:
            lines.append(f"Location: {reminder.location}")
        if reminder.meet_link and not cancelled:
            lines += ["", f"Join with Google Meet: {reminder.meet_link}"]
        text = "\n".join(lines)

        # ---- html
        rows = [
            f'<h2 style="margin:0 0 8px;font-size:20px">{escape(reminder.title)}</h2>',
            f"<p>{escape(intro)}</p>",
        ]
        if description:
            rows.append(
                '<p style="margin:12px 0 4px"><strong>Description</strong></p>'
                '<div style="white-space:pre-wrap;margin:0 0 12px">'
                f"{escape(description)}</div>"
            )
        rows.append(f"<p><strong>When:</strong> {escape(when)}</p>")
        if reminder.host_name:
            rows.append(f"<p><strong>Host:</strong> {escape(reminder.host_name)}</p>")
        if reminder.location:
            rows.append(f"<p><strong>Location:</strong> {escape(reminder.location)}</p>")
        if reminder.meet_link and not cancelled:
            link = escape(reminder.meet_link, quote=True)
            rows.append(f'<p><a href="{link}">Join with Google Meet</a></p>')
            rows.append(f'<p style="color:#666;font-size:12px">{link}</p>')
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
