from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def build_reset_link(reset_token: str) -> str:
    """Absolute link to the frontend's reset-password page.

    Fails loudly when FRONTEND_URL is missing — otherwise users receive a
    broken "None/reset-password?token=..." link.
    """
    base_url = (settings.FRONTEND_URL or "").strip().rstrip("/")

    if not base_url:
        raise ImproperlyConfigured(
            "FRONTEND_URL is not set; cannot build the password reset link."
        )

    return f"{base_url}/reset-password?token={quote(reset_token, safe='')}"
