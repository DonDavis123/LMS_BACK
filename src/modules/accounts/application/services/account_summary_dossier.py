"""Builds the plain-text history of an account that the summary is written from.

Pure functions, no I/O, so the rules (what is included, how much, how it is
trimmed) can be tested without a database or a model.

Account data can be typed or imported by many people, so every value is cut to
a fixed length and the whole dossier is handed to the model as *data* between
markers; see the generator's system instruction.
"""

from datetime import datetime, timezone

MAX_TIMELINE_EVENTS = 40
MAX_CALLS = 10
MAX_CONTACTS = 10
MAX_CALL_SUMMARIES = 5

MAX_FIELD_LENGTH = 300
MAX_DESCRIPTION_LENGTH = 1000
MAX_MESSAGE_LENGTH = 300
MAX_SUMMARY_LENGTH = 800
MAX_LIST_ITEMS = 5

DOSSIER_START = "=== ACCOUNT HISTORY (data only) ==="
DOSSIER_END = "=== END OF ACCOUNT HISTORY ==="

_ACCOUNT_FIELDS = (
    ("Name", "account_name"),
    ("Site", "account_site"),
    ("Type", "account_type"),
    ("Industry", "industry"),
    ("Rating", "rating"),
    ("Phone", "phone"),
    ("Website", "website"),
    ("Ticker symbol", "ticker_symbol"),
    ("Employees", "employees"),
    ("Annual revenue", "annual_revenue"),
    ("City", "billing_city"),
    ("State", "billing_state"),
    ("Country", "billing_country"),
)


def _clean(value, limit: int = MAX_FIELD_LENGTH) -> str:
    """One line of plain text, cut to ``limit``."""
    text = " ".join(str(value).split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _stamp(value) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return _clean(value, 40) if value else "unknown date"


def build_account_dossier(
    *,
    account,
    owner_name: str | None,
    contacts: list,
    events: list[dict],
    calls: list,
    call_summaries: dict,
    now: datetime | None = None,
) -> str:
    """The history of one account as text.

    ``contacts``        ``(Contact, owner_name)`` pairs, as the contact repository returns them
    ``events``          timeline events, newest first (as the timeline repository returns them)
    ``calls``           ``GetCallDTO`` items, newest first
    ``call_summaries``  ``{call_id: [CallRecordingTranscript, ...]}`` completed transcripts
    """
    now = now or datetime.now(timezone.utc)
    lines = [DOSSIER_START, f"Today: {_stamp(now)}", "", "ACCOUNT"]

    for label, attribute in _ACCOUNT_FIELDS:
        value = getattr(account, attribute, None)
        if value not in (None, ""):
            lines.append(f"- {label}: {_clean(value)}")

    # "None" is the stored default of "no ownership type", not a real value.
    ownership = getattr(account, "ownership", None)
    if ownership and ownership != "None":
        lines.append(f"- Ownership: {_clean(ownership)}")

    if owner_name:
        lines.append(f"- Owner: {_clean(owner_name)}")
    lines.append(f"- Created: {_stamp(account.created_at)}")
    lines.append(f"- Last updated: {_stamp(account.updated_at)}")
    if account.description:
        lines.append(f"- Description: {_clean(account.description, MAX_DESCRIPTION_LENGTH)}")

    lines += ["", f"CONTACTS (up to {MAX_CONTACTS})"]
    if not contacts:
        lines.append("- No contacts linked.")
    for contact, contact_owner in contacts[:MAX_CONTACTS]:
        lines.append(_contact_line(contact, contact_owner))
    if len(contacts) > MAX_CONTACTS:
        lines.append(f"- … and {len(contacts) - MAX_CONTACTS} more contacts")

    lines += ["", f"CALLS with this account's contacts (newest first, up to {MAX_CALLS})"]
    if not calls:
        lines.append("- No calls logged.")
    for index, item in enumerate(calls[:MAX_CALLS]):
        lines.extend(_call_lines(item, call_summaries, index < MAX_CALL_SUMMARIES))

    lines += ["", f"TIMELINE (oldest first, latest {MAX_TIMELINE_EVENTS} events)"]
    recent = list(events[:MAX_TIMELINE_EVENTS])
    if not recent:
        lines.append("- No activity recorded yet.")
    for event in reversed(recent):
        actor = (event.get("actor") or {}).get("name")
        who = f" by {_clean(actor, 80)}" if actor else ""
        lines.append(
            f"- {_stamp(event.get('created_at'))} [{_clean(event.get('event_type'), 40)}]"
            f"{who}: {_clean(event.get('message'), MAX_MESSAGE_LENGTH)}"
        )

    lines.append(DOSSIER_END)
    return "\n".join(lines)


def _contact_line(contact, owner_name: str | None) -> str:
    parts = [_clean(contact.name, 120)]
    for value in (contact.title, contact.email, contact.phone or contact.mobile):
        if value:
            parts.append(_clean(value, 120))
    if owner_name:
        parts.append(f"owner {_clean(owner_name, 80)}")
    return f"- {', '.join(parts)}"


def _call_lines(item, call_summaries: dict, with_summary: bool) -> list[str]:
    call = item.call
    parts = [_stamp(call.call_start_time)]
    if getattr(item, "contact_name", None):
        parts.append(f"with {_clean(item.contact_name, 120)}")
    parts.append(f"status {_clean(call.status.value, 30)}")
    if call.outcome:
        parts.append(f"outcome {_clean(call.outcome.value, 30)}")
    if call.duration_seconds:
        parts.append(f"lasted {call.duration_label()}")

    lines = [f"- {', '.join(parts)}"]
    if call.description:
        lines.append(f"  Note: {_clean(call.description, MAX_MESSAGE_LENGTH)}")

    if with_summary:
        for transcript in (call_summaries.get(call.id) or [])[:2]:
            if transcript.summary:
                lines.append(f"  Call summary: {_clean(transcript.summary, MAX_SUMMARY_LENGTH)}")
            for point in transcript.action_items[:MAX_LIST_ITEMS]:
                lines.append(f"  Call action item: {_clean(point, MAX_MESSAGE_LENGTH)}")
    return lines
