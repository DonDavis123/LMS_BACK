"""Builds the detailed, record-wide call history from timeline events.

Timeline events only store *what changed* when a call is edited, so each event
is paired with a snapshot of the call (start time, duration, outcome, type and
notes) as it was at that moment. Snapshots are rebuilt from the call's current
state by undoing later edits, so they are exact for calls logged before this
feature existed too.
"""

from datetime import datetime
from typing import Any

CALL_EVENT_PREFIX = "CALL_"

SNAPSHOT_FIELDS = (
    "call_start_time",
    "duration_seconds",
    "call_type",
    "outcome",
    "description",
)


def format_duration(total_seconds: int | None) -> str | None:
    """``4 min 10 sec`` — mirrors ``Call.duration_label``."""
    if total_seconds is None:
        return None

    hours, remainder = divmod(int(total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours} hr {minutes} min {seconds} sec"
    if minutes:
        return f"{minutes} min {seconds} sec"
    return f"{seconds} sec"


def _event_call_id(event: dict) -> str | None:
    call_id = (event.get("metadata") or {}).get("call_id")
    return str(call_id) if call_id else None


def _event_changes(event: dict) -> dict:
    return (event.get("metadata") or {}).get("changes") or {}


def _coerce(field: str, value: Any) -> Any:
    # Timeline metadata stores datetimes as ISO strings.
    if field == "call_start_time" and isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _snapshots_for_live_call(call_events: list[dict], current: dict) -> dict:
    """Walk newest -> oldest, undoing each edit to get the state before it."""
    state = dict(current)
    snapshots = {}

    for event in call_events:  # newest first
        snapshots[event["id"]] = dict(state)

        if event["event_type"] == "CALL_UPDATED":
            for field, change in _event_changes(event).items():
                if field in SNAPSHOT_FIELDS:
                    state[field] = _coerce(field, change.get("old_value"))

    return snapshots


def _snapshots_for_removed_call(call_events: list[dict]) -> dict:
    """A deleted call has no live row: rebuild what we can from its events."""
    state: dict = {}
    snapshots = {}

    for event in reversed(call_events):  # oldest first
        metadata = event.get("metadata") or {}

        if event["event_type"] == "CALL_UPDATED":
            for field, change in _event_changes(event).items():
                if field in SNAPSHOT_FIELDS:
                    state[field] = _coerce(field, change.get("new_value"))
        else:
            for field in ("outcome", "duration_seconds", "description"):
                if field in metadata and field not in state:
                    state[field] = metadata[field]

        snapshots[event["id"]] = dict(state)

    return snapshots


def build_record_history(
    events: list[dict],
    live_calls: dict[str, dict],
) -> list[dict]:
    """Return call events (newest first), each with a ``call`` snapshot.

    ``events``     timeline events of the lead/contact, newest first.
    ``live_calls`` active calls of the record keyed by call id; each value has
                   the ``SNAPSHOT_FIELDS`` plus ``owner_name``.
    """
    call_events = [
        event for event in events
        if str(event.get("event_type", "")).startswith(CALL_EVENT_PREFIX)
    ]

    by_call: dict[str | None, list[dict]] = {}
    for event in call_events:
        by_call.setdefault(_event_call_id(event), []).append(event)

    snapshots: dict = {}
    for call_id, group in by_call.items():
        live = live_calls.get(call_id) if call_id else None
        if live is not None:
            snapshots.update(_snapshots_for_live_call(group, live))
        else:
            snapshots.update(_snapshots_for_removed_call(group))

    history = []
    for event in call_events:
        call_id = _event_call_id(event)
        snapshot = snapshots.get(event["id"], {})
        live = live_calls.get(call_id) if call_id else None
        duration = snapshot.get("duration_seconds")

        history.append(
            {
                "id": event["id"],
                "event_type": event["event_type"],
                "call_id": call_id,
                "actor": event["actor"],
                "message": event["message"],
                "changes": _event_changes(event),
                "created_at": event["created_at"],
                "call": {
                    "call_start_time": snapshot.get("call_start_time"),
                    "call_type": snapshot.get("call_type"),
                    "outcome": snapshot.get("outcome"),
                    "duration_seconds": duration,
                    "duration_label": format_duration(duration),
                    "description": snapshot.get("description"),
                    "owner_name": live.get("owner_name") if live else None,
                },
            }
        )

    return history
