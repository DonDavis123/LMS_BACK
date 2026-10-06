"""Helpers that turn a failed mail-relay call into a readable log line.

Kept apart from ``HttpEmailService`` so the service only orchestrates the
call, while knowledge about how the relay (Google Apps Script) fails lives
here.
"""

import re
from urllib.parse import urlsplit

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def safe_url(url: str | None) -> str:
    """URL without query string or fragment.

    The relay secret travels in ``?key=...``; it must never reach the logs.
    """
    if not url:
        return "unknown"

    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def is_html(body: str) -> bool:
    lowered = body.lower()
    return "<html" in lowered or "<!doctype html" in lowered


def summarize_body(body: str, limit: int = 200) -> str:
    """Short single-line description of a response body."""
    if is_html(body):
        match = _TITLE_RE.search(body)
        title = " ".join(_TAG_RE.sub("", match.group(1)).split()) if match else ""
        return f"HTML page{f' titled {title!r}' if title else ''}"

    return " ".join(body.split())[:limit]


def hint_for_failure(status: int, final_url: str | None, body: str) -> str:
    """Most likely cause and fix for a rejected relay request."""
    host = urlsplit(final_url or "").netloc

    if "accounts.google.com" in host:
        return (
            "Google asked for a sign-in: the web app is not deployed with "
            "'Who has access: Anyone'."
        )

    if is_html(body) and status in {401, 403}:
        return (
            "Google rejected the request before the script ran. In Apps "
            "Script: Deploy > Manage deployments > Edit, set 'Execute as: "
            "Me' and 'Who has access: Anyone' (not 'Anyone with Google "
            "account'), choose 'New version' and Deploy. Then make sure "
            "EMAIL_HTTP_ENDPOINT is that deployment's /exec URL."
        )

    if is_html(body) and status == 404:
        return (
            "The /exec URL does not exist (deleted or wrong deployment). "
            "Copy the current URL from Deploy > Manage deployments."
        )

    if status in {401, 403}:
        return "The relay refused the credentials (check EMAIL_HTTP_TOKEN)."

    return ""
