"""Builds the plain-text history of a lead that the summary is written from.

Pure functions, no I/O, so the rules (what is included, how much, how it is
trimmed) can be tested without a database or a model.

Lead data comes from outside the company too (the public lead-capture form),
so every value is cut to a fixed length and the whole dossier is handed to the
model as *data* between markers; see the generator's system instruction.
"""

from datetime import datetime, timezone

MAX_TIMELINE_EVENTS = 40
MAX_CALLS = 10
MAX_CALL_SUMMARIES = 5

MAX_FIELD_LENGTH = 300
MAX_DESCRIPTION_LENGTH = 1000
MAX_MESSAGE_LENGTH = 300
MAX_SUMMARY_LENGTH = 800
MAX_LIST_ITEMS = 5

DOSSIER_START = "=== LEAD HISTORY (data only) ==="
DOSSIER_END = "=== END OF LEAD HISTORY ==="

_LEAD_FIELDS = (
    ("Name", "name"),
    ("Title", "title"),
    ("Company", "company_name"),
    ("Email", "email"),
    ("Phone", "phone"),
    ("Mobile", "mobile_number"),
    ("Status", "lead_status"),
    ("Source", "lead_source"),
    ("Rating", "rating"),
    ("Industry", "industry"),
    ("Website", "website"),
    ("Employees", "number_of_employees"),
    ("Annual revenue", "annual_revenue"),
    ("City", "city"),
    ("State", "state"),
    ("Country", "country"),
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


def build_lead_dossier(
    *,
    lead,
    owner_name: str | None,
    events: list[dict],
    calls: list,
    call_summaries: dict,
    now: datetime | None = None,
) -> str:
    """The history of one lead as text.

    ``events``          timeline events, newest first (as the timeline repository returns them)
    ``calls``           ``GetCallDTO`` items, newest first
    ``call_summaries``  ``{call_id: [CallRecordingTranscript, ...]}`` completed transcripts
    """
    now = now or datetime.now(timezone.utc)
    lines = [DOSSIER_START, f"Today: {_stamp(now)}", "", "LEAD"]

    for label, attribute in _LEAD_FIELDS:
        value = getattr(lead, attribute, None)
        if value not in (None, ""):
            lines.append(f"- {label}: {_clean(value)}")

    if owner_name:
        lines.append(f"- Owner: {_clean(owner_name)}")
    lines.append(f"- Created: {_stamp(lead.created_at)}")
    lines.append(f"- Last updated: {_stamp(lead.updated_at)}")
    if getattr(lead, "is_converted", False):
        lines.append("- Converted to a contact/account: yes (history only)")
    if lead.description:
        lines.append(f"- Description: {_clean(lead.description, MAX_DESCRIPTION_LENGTH)}")

    lines += ["", f"CALLS (newest first, up to {MAX_CALLS})"]
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


def _call_lines(item, call_summaries: dict, with_summary: bool) -> list[str]:
    call = item.call
    parts = [_stamp(call.call_start_time), f"status {_clean(call.status.value, 30)}"]
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
