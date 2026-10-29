"""Undo of a lead import: every rule in one place.

Nothing here knows about HTTP or Django. The data comes in through a *store*
(``infrastructure/lead_import_undo_store.py``), so the preview, the real undo
and a test with fakes all run exactly the same code.

THE RULES, in plain words
-------------------------
* Undo only ever touches ids the import stored on its own job: the leads whose
  ``import_job`` is this job, the accounts and contacts in
  ``options["converted"]``, and the leads in ``update_snapshots``. All of it
  inside the job's own company. Nothing comes from the request.
* Nothing is deleted for good. "Removed" means ``is_deleted = True``.
* A record is removed only while it is **untouched**:

  - lead: not deleted, ``updated_at`` still equals the moment it was created
    (see ``is_untouched``), nobody added a task, call, meeting or timeline
    entry to it, and it was not converted by hand;
  - account / contact: not deleted, ``updated_at`` still equals the moment it
    was created and ``modified_by`` is still its creator, and nothing else
    uses it (tasks, calls, meetings, other contacts, timeline entries);
    contacts removed by this same undo do not count as "something else".
* A lead the import UPDATED is restored from ``update_snapshots`` only when
  every field the import changed still holds the value the import wrote
  (``options["update_applied"]``). If any of them was changed again, the lead is
  left alone as a whole.
* Accounts and contacts the import only REUSED are never touched.
* Anything left alone is reported (kind, name, reason); the job ends
  ``partly_undone`` instead of ``undone``. A later attempt looks at the
  leftovers again and never repeats what is already done.

THE "UNTOUCHED" TEST (the approach chosen)
-----------------------------------------
Every row the database creates gets ``created_at`` and ``updated_at`` from two
back-to-back clock reads, so they differ by microseconds; a lead that the
import created and then converted differs by milliseconds (the conversion
saves it once more, inside the same row). Any later save through the app
(edit, assign, owner transfer, convert) sets ``updated_at`` to the time of that
save, which is seconds, minutes or days later. So::

    untouched  <=>  updated_at - created_at <= UNTOUCHED_TOLERANCE (3 s)

Nothing has to be stored per lead (no map to grow and to keep in step), it
also catches an edit made WHILE the import was still running (a comparison with
``finished_at`` cannot), and it needs no change to the import code for created
records. Accounts and contacts are built with ``created_at == updated_at``, so
the same test holds there.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable
from uuid import UUID

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_UNDONE = "undone"
STATUS_PARTLY_UNDONE = "partly_undone"

STAGE_DRAFT = "draft"
STAGE_RUNNING = "running"

CHUNK_SIZE = 500
MAX_EXAMPLES = 20
MAX_STORED_LEFT_ALONE = 1000
UNTOUCHED_TOLERANCE = timedelta(seconds=3)
# An undo that claimed the job and then died (server restart) is taken over
# after this long.
UNDO_CLAIM_TIMEOUT = timedelta(minutes=10)

EVENT_UNDONE = "lead_import_undone"
TIMELINE_MESSAGE_LIMIT = 500

# Lead fields an import update can have written (and undo may write back).
RESTORABLE_FIELDS = frozenset({
    "name", "title", "company_name", "email", "mobile_number", "phone",
    "lead_source", "lead_status", "industry", "rating", "website",
    "number_of_employees", "annual_revenue", "owner_id", "address", "city",
    "state", "country", "postal_code", "description",
})
# Columns that can never be empty: an old value of None means corrupt data.
NOT_NULL_FIELDS = frozenset({
    "name", "lead_source", "lead_status", "industry", "rating", "owner_id",
})

# What a left-alone item is.
KIND_LEAD = "lead"
KIND_ACCOUNT = "account"
KIND_CONTACT = "contact"
KIND_UPDATED_LEAD = "updated_lead"

# Why it is left alone.
CODE_EDITED = "edited"
CODE_ACTIVITY = "activity"
CODE_CONVERTED = "converted"
CODE_IN_USE = "in_use"
CODE_CHANGED_SINCE = "changed_since"
CODE_NO_IMPORTED_VALUES = "no_imported_values"
CODE_RESTORE_UNAVAILABLE = "restore_unavailable"

_GROUP_REASONS = {
    (KIND_LEAD, CODE_EDITED): "Edited, assigned or reassigned after the import.",
    (KIND_LEAD, CODE_ACTIVITY): (
        "Has a task, call, meeting or other activity added after the import."
    ),
    (KIND_LEAD, CODE_CONVERTED): "Converted by hand after the import.",
    (KIND_ACCOUNT, CODE_EDITED): "Edited after the import.",
    (KIND_ACCOUNT, CODE_IN_USE): "Used by other records.",
    (KIND_CONTACT, CODE_EDITED): "Edited after the import.",
    (KIND_CONTACT, CODE_IN_USE): "Used by other records.",
    (KIND_UPDATED_LEAD, CODE_CHANGED_SINCE): (
        "Changed again after the import, so the old values were not put back."
    ),
    (KIND_UPDATED_LEAD, CODE_CONVERTED): "Converted after the import.",
    (KIND_UPDATED_LEAD, CODE_NO_IMPORTED_VALUES): (
        "The values the import wrote were not recorded, so it cannot be checked."
    ),
    (KIND_UPDATED_LEAD, CODE_RESTORE_UNAVAILABLE): (
        "The old values are no longer stored, so these leads cannot be restored."
    ),
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _options(job) -> dict:
    return job.options if isinstance(job.options, dict) else {}


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_iso(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _id_list(value) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _as_uuid(value) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def normalize(value):
    """A value in the form used to compare "now" with "what the import wrote":
    blank text is None, everything else is compared as trimmed text."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def same_value(left, right) -> bool:
    """Two stored values are the same value. Blank equals blank, and numbers
    are compared as numbers (``1000`` and ``1000.00`` are the same revenue)."""
    first, second = normalize(left), normalize(right)
    if first == second:
        return True
    if first is None or second is None:
        return False
    try:
        return Decimal(first) == Decimal(second)
    except (InvalidOperation, ValueError):
        return False


def is_untouched(created_at, updated_at) -> bool:
    """True while a record still looks exactly as it was created (see the
    module text)."""
    if created_at is None or updated_at is None:
        return False
    return (updated_at - created_at) <= UNTOUCHED_TOLERANCE


# ---------------------------------------------------------------------------
# Who may undo, and when (shared by the report, the preview and the undo)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UndoEligibility:
    can_undo: bool
    code: str | None = None
    reason: str | None = None
    how_to_fix: str | None = None
    status_code: int = 400


def undo_running(job, now: datetime | None = None) -> bool:
    """An undo of this job has been claimed and has not timed out."""
    state = _options(job).get("undo")
    if not isinstance(state, dict) or state.get("state") != "running":
        return False
    started = _parse_iso(state.get("run_started_at"))
    if started is None:
        return False
    return (now or datetime.now(timezone.utc)) - started < UNDO_CLAIM_TIMEOUT


def undo_eligibility(job, now: datetime | None = None) -> UndoEligibility:
    """Whether an undo may be started for this job, from the job alone.

    The preview adds what only the data can tell (is anything left that can
    still be removed or restored). Purged rows never matter: undo works from
    ids and snapshots.
    """
    options = _options(job)

    if options.get("stage") == STAGE_DRAFT:
        return UndoEligibility(
            False, "import_not_started",
            "This import has not been started yet.",
            "Start the import first; only an import that has run can be undone.",
        )
    if job.status == STATUS_UNDONE:
        return UndoEligibility(
            False, "already_undone",
            "This import has already been undone.",
            "Nothing more to do. The import history shows what was removed.",
        )
    if job.status in (STATUS_QUEUED, STATUS_PROCESSING) or options.get("stage") == STAGE_RUNNING:
        return UndoEligibility(
            False, "import_still_running",
            "This import is still running.",
            "Wait until it has finished (or cancel it), then undo it.",
        )
    if job.status not in (STATUS_COMPLETED, STATUS_FAILED, STATUS_PARTLY_UNDONE):
        return UndoEligibility(
            False, "import_not_undoable",
            "This import cannot be undone.",
            "Open the import history to see its state.",
        )
    if undo_running(job, now):
        return UndoEligibility(
            False, "undo_in_progress",
            "An undo of this import is already running.",
            "Wait a moment and open the import history to see the result.",
            status_code=409,
        )
    if job.status != STATUS_PARTLY_UNDONE:
        changed = _int(job.created_count) + _int(job.updated_count)
        if changed == 0:
            return UndoEligibility(
                False, "nothing_to_undo",
                "This import did not add or change any leads, so there is nothing to undo.",
                "No action is needed.",
            )
    return UndoEligibility(True)


# ---------------------------------------------------------------------------
# What the passes find
# ---------------------------------------------------------------------------

@dataclass
class LeftAlone:
    kind: str
    code: str
    id: str | None
    name: str | None
    detail: str | None = None

    @property
    def reason(self) -> str:
        base = _GROUP_REASONS.get((self.kind, self.code), "Left alone.")
        return f"{base} ({self.detail})" if self.detail else base

    def as_item(self) -> dict:
        return {
            "kind": self.kind,
            "id_or_name": self.name or self.id,
            "id": self.id,
            "reason": self.reason,
            "code": self.code,
        }


@dataclass
class UndoRun:
    """The result of one pass over a job (``dry_run`` = nothing was written)."""

    dry_run: bool
    removed_leads: int = 0
    removed_contacts: int = 0
    removed_accounts: int = 0
    restored_leads: int = 0
    already_deleted: int = 0
    reused_accounts: int = 0
    reused_contacts: int = 0
    restore_unavailable_reason: str | None = None
    left_alone: list[LeftAlone] = field(default_factory=list)
    left_alone_counts: Counter = field(default_factory=Counter)
    # Items beyond MAX_STORED_LEFT_ALONE: counted, but not listed one by one.
    left_alone_omitted: int = 0
    removed_contact_ids: set = field(default_factory=set)
    # First lead of each kind, for the timeline entry to hang on.
    first_left_alone_lead: str | None = None
    first_restored_lead: str | None = None
    first_removed_lead: str | None = None

    @property
    def left_alone_total(self) -> int:
        return sum(self.left_alone_counts.values())

    @property
    def actions(self) -> int:
        return (
            self.removed_leads + self.removed_contacts
            + self.removed_accounts + self.restored_leads
        )

    def add_left_alone(self, item: LeftAlone, count: int = 1) -> None:
        self.left_alone_counts[(item.kind, item.code)] += count
        if len(self.left_alone) < MAX_STORED_LEFT_ALONE:
            self.left_alone.append(item)
        else:
            self.left_alone_omitted += count
        if item.kind in (KIND_LEAD, KIND_UPDATED_LEAD) and self.first_left_alone_lead is None:
            self.first_left_alone_lead = item.id

    def anchor_lead_id(self) -> str | None:
        return (
            self.first_left_alone_lead
            or self.first_restored_lead
            or self.first_removed_lead
        )


def left_alone_groups(run: UndoRun) -> list[dict]:
    return [
        {
            "kind": kind,
            "code": code,
            "reason": _GROUP_REASONS.get((kind, code), "Left alone."),
            "count": count,
        }
        for (kind, code), count in sorted(run.left_alone_counts.items())
    ]


# ---------------------------------------------------------------------------
# The passes
# ---------------------------------------------------------------------------

_ACTIVITY_LABELS = {
    "task": "a task",
    "call": "a call",
    "meeting": "a meeting",
    "timeline": "a timeline entry",
}


def _lead_block(row: dict, expected_converted: bool, activity: str | None):
    """``(code, detail)`` when a created lead must be left alone, else None."""
    if bool(row["is_converted"]) != expected_converted:
        if row["is_converted"]:
            return CODE_CONVERTED, None
        return CODE_EDITED, None
    if not is_untouched(row["created_at"], row["updated_at"]):
        return CODE_EDITED, None
    if activity:
        return CODE_ACTIVITY, _ACTIVITY_LABELS.get(activity, activity)
    return None


def _chunks(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _run_chunk(work: Callable, dry_run: bool, transaction_manager):
    """A dry run reads only; a real run does each chunk in its own transaction."""
    if dry_run or transaction_manager is None:
        return work()
    return transaction_manager.execute(work)


def run_undo(
    job,
    store,
    *,
    dry_run: bool,
    snapshots: dict | None = None,
    transaction_manager=None,
    actor_id=None,
    now: datetime | None = None,
) -> UndoRun:
    """Look at (``dry_run=True``) or carry out (``dry_run=False``) an undo.

    Order: created leads, created contacts, created accounts (so an account is
    not held back by a contact this same undo removes), then restores.
    ``store`` is company- and job-scoped; see ``DjangoUndoStore``.
    """
    options = _options(job)
    converted = options.get("converted") if isinstance(options.get("converted"), dict) else {}
    now = now or datetime.now(timezone.utc)
    run = UndoRun(dry_run=dry_run)
    run.reused_accounts = len(_id_list(converted.get("accounts_reused")))
    run.reused_contacts = len(_id_list(converted.get("contacts_reused")))

    _pass_leads(store, run, set(_id_list(converted.get("leads"))), now, transaction_manager)
    _pass_contacts(
        store, run, _id_list(converted.get("contacts_created")), now, actor_id,
        transaction_manager,
    )
    _pass_accounts(
        store, run, _id_list(converted.get("accounts_created")), now, actor_id,
        transaction_manager,
    )
    _pass_restores(
        job, store, run, snapshots or {}, options.get("update_applied"), now,
        transaction_manager,
    )
    return run


def _progress(store, run: UndoRun, **delta) -> None:
    """Counters saved with each chunk, so an interrupted undo loses nothing."""
    if not run.dry_run:
        store.add_progress({key: value for key, value in delta.items() if value})


def _pass_leads(store, run: UndoRun, converted_ids: set, now, transaction_manager) -> None:
    after = None
    while True:
        def work(after=after):
            rows = store.job_lead_rows(after, CHUNK_SIZE, lock=not run.dry_run)
            if not rows:
                return None
            live = [row for row in rows if not row["is_deleted"]]
            run.already_deleted += len(rows) - len(live)
            activity = store.lead_activity([row["id"] for row in live]) if live else {}

            removable = []
            for row in live:
                block = _lead_block(
                    row, str(row["id"]) in converted_ids, activity.get(row["id"])
                )
                if block is None:
                    removable.append(row["id"])
                    if run.first_removed_lead is None:
                        run.first_removed_lead = str(row["id"])
                    continue
                code, detail = block
                run.add_left_alone(
                    LeftAlone(KIND_LEAD, code, str(row["id"]), row.get("name"), detail)
                )
            if removable and not run.dry_run:
                store.soft_delete_leads(removable, now)
            run.removed_leads += len(removable)
            _progress(store, run, leads_removed=len(removable))
            return rows[-1]["id"]

        after = _run_chunk(work, run.dry_run, transaction_manager)
        if after is None:
            return


def _in_use_detail(labels: list[str]) -> str:
    return ", ".join(sorted(set(labels)))


def _pass_contacts(store, run, ids, now, actor_id, transaction_manager) -> None:
    for chunk in _chunks(ids, CHUNK_SIZE):
        def work(chunk=chunk):
            rows = store.contact_rows(chunk, lock=not run.dry_run)
            live = [row for row in rows if not row["is_deleted"]]
            run.already_deleted += len(rows) - len(live)

            removable, untouched = [], []
            for row in live:
                if (
                    is_untouched(row["created_at"], row["updated_at"])
                    and row["modified_by_id"] == row["created_by_id"]
                ):
                    untouched.append(row)
                else:
                    run.add_left_alone(
                        LeftAlone(KIND_CONTACT, CODE_EDITED, str(row["id"]), row.get("name"))
                    )
            blockers = (
                store.contact_blockers([row["id"] for row in untouched]) if untouched else {}
            )
            for row in untouched:
                labels = blockers.get(row["id"])
                if labels:
                    run.add_left_alone(LeftAlone(
                        KIND_CONTACT, CODE_IN_USE, str(row["id"]), row.get("name"),
                        _in_use_detail(labels),
                    ))
                else:
                    removable.append(row["id"])
            if removable and not run.dry_run:
                store.soft_delete_contacts(removable, now, actor_id)
            run.removed_contacts += len(removable)
            run.removed_contact_ids.update(removable)
            _progress(store, run, contacts_removed=len(removable))

        _run_chunk(work, run.dry_run, transaction_manager)


def _pass_accounts(store, run, ids, now, actor_id, transaction_manager) -> None:
    for chunk in _chunks(ids, CHUNK_SIZE):
        def work(chunk=chunk):
            rows = store.account_rows(chunk, lock=not run.dry_run)
            live = [row for row in rows if not row["is_deleted"]]
            run.already_deleted += len(rows) - len(live)

            removable, untouched = [], []
            for row in live:
                if (
                    is_untouched(row["created_at"], row["updated_at"])
                    and row["modified_by_id"] == row["created_by_id"]
                ):
                    untouched.append(row)
                else:
                    run.add_left_alone(LeftAlone(
                        KIND_ACCOUNT, CODE_EDITED, str(row["id"]), row.get("account_name"),
                    ))
            blockers = (
                store.account_blockers(
                    [row["id"] for row in untouched], run.removed_contact_ids
                )
                if untouched else {}
            )
            for row in untouched:
                labels = blockers.get(row["id"])
                if labels:
                    run.add_left_alone(LeftAlone(
                        KIND_ACCOUNT, CODE_IN_USE, str(row["id"]), row.get("account_name"),
                        _in_use_detail(labels),
                    ))
                else:
                    removable.append(row["id"])
            if removable and not run.dry_run:
                store.soft_delete_accounts(removable, now, actor_id)
            run.removed_accounts += len(removable)
            _progress(store, run, accounts_removed=len(removable))

        _run_chunk(work, run.dry_run, transaction_manager)


def _classify_restore(snapshot: dict, applied: dict | None, row: dict):
    """``("restore", {field: old})``, ``("done", None)`` or
    ``("blocked", (code, detail))`` for one updated lead."""
    if row["is_converted"]:
        return "blocked", (CODE_CONVERTED, None)
    if not isinstance(applied, dict) or not applied:
        return "blocked", (CODE_NO_IMPORTED_VALUES, None)

    to_restore, changed_again = {}, []
    for name, old in snapshot.items():
        if name not in RESTORABLE_FIELDS:
            continue
        if name not in applied:
            return "blocked", (CODE_NO_IMPORTED_VALUES, None)
        current = row.get(name)
        written = applied.get(name)
        if same_value(current, written):
            if not same_value(written, old):
                if normalize(old) is None and name in NOT_NULL_FIELDS:
                    changed_again.append(name)
                else:
                    to_restore[name] = old
        elif not same_value(current, old):
            changed_again.append(name)

    if changed_again:
        return "blocked", (CODE_CHANGED_SINCE, ", ".join(sorted(changed_again)))
    if to_restore:
        return "restore", to_restore
    return "done", None


def _pass_restores(job, store, run, snapshots, applied_map, now, transaction_manager) -> None:
    updated_count = _int(job.updated_count)
    if not snapshots:
        if updated_count > 0:
            run.restore_unavailable_reason = (
                f"The old values of the {updated_count:,} updated "
                f"{_plural(updated_count, 'lead', 'leads')} are no longer stored, so "
                "they cannot be restored. Everything else can still be undone."
            )
            run.add_left_alone(
                LeftAlone(KIND_UPDATED_LEAD, CODE_RESTORE_UNAVAILABLE, None, None),
                count=updated_count,
            )
        return

    applied_map = applied_map if isinstance(applied_map, dict) else {}
    ids = []
    for key in snapshots:
        parsed = _as_uuid(key)
        if parsed is not None:
            ids.append(parsed)

    for chunk in _chunks(ids, CHUNK_SIZE):
        def work(chunk=chunk):
            rows = store.lead_rows_for_restore(chunk, lock=not run.dry_run)
            changes: dict = {}
            for lead_id in chunk:
                row = rows.get(lead_id)
                if row is None or row["is_deleted"]:
                    run.already_deleted += 1
                    continue
                snapshot = snapshots.get(str(lead_id))
                if not isinstance(snapshot, dict):
                    continue
                verdict, detail = _classify_restore(
                    snapshot, applied_map.get(str(lead_id)), row
                )
                if verdict == "restore":
                    changes[lead_id] = detail
                    if run.first_restored_lead is None:
                        run.first_restored_lead = str(lead_id)
                elif verdict == "blocked":
                    code, extra = detail
                    run.add_left_alone(
                        LeftAlone(KIND_UPDATED_LEAD, code, str(lead_id), row.get("name"), extra)
                    )
            if changes and not run.dry_run:
                store.restore_lead_fields(changes, now)
            run.restored_leads += len(changes)
            _progress(store, run, leads_restored=len(changes))

        _run_chunk(work, run.dry_run, transaction_manager)


# ---------------------------------------------------------------------------
# Words and JSON
# ---------------------------------------------------------------------------

def _short_name(file_name: str) -> str:
    name = (file_name or "").strip() or "the file"
    return name if len(name) <= 100 else name[:97] + "..."


def counts_message(file_name: str, counts: dict) -> str:
    """``Undid import of clients.xlsx: 1,150 leads removed, 30 restored, 4 left alone``"""
    leads = int(counts.get("leads_removed") or 0)
    accounts = int(counts.get("accounts_removed") or 0)
    contacts = int(counts.get("contacts_removed") or 0)
    restored = int(counts.get("leads_restored") or 0)
    left = int(counts.get("left_alone") or 0)

    parts = [f"{leads:,} {_plural(leads, 'lead', 'leads')} removed"]
    if accounts:
        parts.append(f"{accounts:,} {_plural(accounts, 'account', 'accounts')} removed")
    if contacts:
        parts.append(f"{contacts:,} {_plural(contacts, 'contact', 'contacts')} removed")
    parts.append(f"{restored:,} restored")
    parts.append(f"{left:,} left alone")
    return f"Undid import of {_short_name(file_name)}: " + ", ".join(parts)


def preview_payload(job, run: UndoRun, eligibility: UndoEligibility) -> dict:
    """The undo-preview JSON. ``run`` is a dry run (or None when not allowed)."""
    base = {
        "job_id": str(job.id),
        "file_name": job.file_name,
        "status": job.status,
        "is_retry": job.status == STATUS_PARTLY_UNDONE,
        "can_undo": eligibility.can_undo,
        "reason_if_not": eligibility.reason,
        "code": eligibility.code,
    }
    if run is None:
        return {
            **base,
            "will_remove_leads": 0,
            "will_remove_accounts": 0,
            "will_remove_contacts": 0,
            "will_restore_updated_leads": 0,
            "will_leave_alone": [],
            "will_leave_alone_count": 0,
            "will_leave_alone_groups": [],
            "already_deleted": 0,
            "reused_accounts_kept": 0,
            "reused_contacts_kept": 0,
            "restore_available": False,
            "restore_note": None,
            "message": eligibility.reason,
        }

    can_undo, reason, message = True, None, None
    if run.actions == 0 and run.left_alone_total > 0:
        can_undo = False
        reason = (
            "Nothing can be undone: every record from this import was changed or used "
            "since it ran, so all of them would be left alone."
        )
        message = reason
    elif run.actions == 0:
        message = (
            "Every record from this import has already been deleted. Undoing will "
            "only mark the import as undone."
        )
    else:
        message = (
            f"Undo will remove {run.removed_leads:,} {_plural(run.removed_leads, 'lead', 'leads')}"
            f", {run.removed_accounts:,} {_plural(run.removed_accounts, 'account', 'accounts')}"
            f" and {run.removed_contacts:,} {_plural(run.removed_contacts, 'contact', 'contacts')}"
            f", restore {run.restored_leads:,} updated "
            f"{_plural(run.restored_leads, 'lead', 'leads')}"
            f" and leave {run.left_alone_total:,} alone. Nothing is deleted permanently."
        )

    return {
        **base,
        "can_undo": can_undo,
        "reason_if_not": reason,
        "code": None if can_undo else "nothing_to_undo",
        "will_remove_leads": run.removed_leads,
        "will_remove_accounts": run.removed_accounts,
        "will_remove_contacts": run.removed_contacts,
        "will_restore_updated_leads": run.restored_leads,
        "will_leave_alone": [item.as_item() for item in run.left_alone[:MAX_EXAMPLES]],
        "will_leave_alone_count": run.left_alone_total,
        "will_leave_alone_groups": left_alone_groups(run),
        "already_deleted": run.already_deleted,
        "reused_accounts_kept": run.reused_accounts,
        "reused_contacts_kept": run.reused_contacts,
        "restore_available": run.restore_unavailable_reason is None,
        "restore_note": run.restore_unavailable_reason,
        "message": message,
    }


def build_undo_report(
    job,
    run: UndoRun,
    counts: dict,
    *,
    attempt: int,
    undone_at: datetime,
    undone_by,
    undone_by_name: str | None,
    status: str,
) -> dict:
    """``options["undo_report"]``: cumulative counts plus what is still left alone."""
    totals = {
        "leads_removed": _int(counts.get("leads_removed")),
        "accounts_removed": _int(counts.get("accounts_removed")),
        "contacts_removed": _int(counts.get("contacts_removed")),
        "leads_restored": _int(counts.get("leads_restored")),
        "left_alone": run.left_alone_total,
        "already_deleted": _int(counts.get("already_deleted")),
    }
    return {
        "attempt": attempt,
        "status": status,
        "undone_at": _iso(undone_at),
        "undone_by": str(undone_by) if undone_by else None,
        "undone_by_name": undone_by_name,
        "message": counts_message(job.file_name, totals),
        "counts": totals,
        "left_alone": {
            "total": run.left_alone_total,
            "groups": left_alone_groups(run),
            "items": [item.as_item() for item in run.left_alone],
            "truncated": run.left_alone_omitted > 0,
        },
        "restore_unavailable_reason": run.restore_unavailable_reason,
    }
