"""Rows of a lead import that are marked "converted" (Account + Contact).

``process_next_batch`` hands the batch's CONVERT outcomes to
``convert_outcomes`` INSIDE the batch transaction. For each row, in its own
savepoint:

1. the lead is created (same fields and defaults as any imported lead, with
   ``import_job`` set, through the processor's lead builder);
2. the Account is reused or created;
3. the Contact is reused or created;
4. ``lead.convert()`` and the lead is saved as converted.

The Account and Contact are built by the SAME functions the Convert Lead
button uses (``lead_conversion``), and an existing Contact is attached to the
Account by the same rule, so a converted import row and a button conversion
give identical records. Nothing is written to the timeline here: the import's
one summary entry is written by ``finalize_job``.

A row that fails is rolled back completely (lead, account and contact of that
row) and returned as a failed ``RowOutcome``; the other rows carry on. Records
are only remembered for later rows after their own row has succeeded.

Existing accounts and contacts for the whole batch are fetched with two
queries (``find_for_import_matching``), never one query per row.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field as dataclass_field
from typing import Callable
from uuid import UUID

from src.modules.leads.application.services.lead_conversion import (
    build_account_from_lead,
    build_contact_from_lead,
    copy_entity,
    has_company_name,
    link_contact_to_account,
)
from src.modules.leads.application.services.lead_import_fields import IMPORT_FIELDS_BY_KEY
from src.modules.leads.application.services.lead_import_options import ImportOptions
from src.modules.leads.application.services.lead_import_pipeline import (
    CONVERT,
    ERROR,
    RowOutcome,
)
from src.modules.leads.application.services.lead_import_validation import RowProblem

logger = logging.getLogger(__name__)

USE_EXISTING = "use_existing"
CODE_CONVERSION_FAILED = "conversion_failed"

# options["converted"] lists never grow beyond this many ids.
MAX_TRACKED_IDS = 10_000

# A phone number needs at least this many digits to be compared at all, and
# only its last 10 digits count (so +1 / 0 prefixes and formatting never matter).
MIN_PHONE_DIGITS = 7
PHONE_KEY_DIGITS = 10
_PHONE_ENDING_DIGITS = 4


class ConversionInternalError(Exception):
    """A row reached the converter that must never be converted. A bug, not a
    problem with the file: the batch is rolled back."""


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

@dataclass
class ConversionContext:
    """Everything ``convert_outcomes`` needs, handed in by the processor."""

    options: ImportOptions
    actor_id: UUID  # the user who started the import: created_by of new records
    lead_repository: object
    account_repository: object
    contact_repository: object
    transaction_manager: object
    # RowOutcome -> Lead (None when the row has no owner). Passed in so a
    # converted lead is built exactly like every other imported lead.
    build_lead: Callable[[RowOutcome], object]
    # {field key: file header}, for problem messages.
    columns: dict = dataclass_field(default_factory=dict)


@dataclass
class ConversionResult:
    converted: list[int] = dataclass_field(default_factory=list)  # row numbers
    failed: list[RowOutcome] = dataclass_field(default_factory=list)
    created_accounts: list[str] = dataclass_field(default_factory=list)
    created_contacts: list[str] = dataclass_field(default_factory=list)
    # Reused = already existed before this row (never one created in this import).
    reused_accounts: list[str] = dataclass_field(default_factory=list)
    reused_contacts: list[str] = dataclass_field(default_factory=list)
    lead_ids: list[str] = dataclass_field(default_factory=list)  # converted leads


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _clean_key(value) -> str | None:
    """Trimmed, lower-case text; None when blank."""
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def phone_key(value) -> str | None:
    """The last 10 digits of a phone number; None when too short to compare."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) < MIN_PHONE_DIGITS:
        return None
    return digits[-PHONE_KEY_DIGITS:]


class _RowFailure(Exception):
    def __init__(self, stage: str, reason: str):
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _reason(exc: Exception, row_number: int) -> str:
    """A plain-English reason for an error raised while converting one row."""
    names = {cls.__name__ for cls in type(exc).__mro__}
    if isinstance(exc, ValueError) and str(exc).strip():
        return str(exc).strip().rstrip(".")
    if "DataError" in names:
        return "a value is too long or in the wrong format for the record"
    if "IntegrityError" in names:
        return "the data conflicts with a record that already exists"
    logger.warning(
        "Lead import: converting row %s failed unexpectedly.", row_number, exc_info=exc
    )
    return "an unexpected error occurred"


# stage -> (field key, message, how to fix)
_STAGES = {
    "lead": (
        "name",
        "Could not add the lead for row {row}: {reason}.",
        "Check the values in this row and upload it again.",
    ),
    "account": (
        "company_name",
        "Could not create the account for row {row}: {reason}.",
        "Fix the company name and upload this row again.",
    ),
    "contact": (
        "name",
        "Could not create the contact for row {row}: {reason}.",
        "Check the name, email and phone in this row and upload it again.",
    ),
    "convert": (
        "converted",
        "Could not mark the lead as converted for row {row}: {reason}.",
        "Upload this row again in a new import.",
    ),
}


def _failure_problem(outcome: RowOutcome, failure: _RowFailure, columns: dict) -> RowProblem:
    field_key, message, how_to_fix = _STAGES.get(failure.stage, _STAGES["lead"])
    definition = IMPORT_FIELDS_BY_KEY.get(field_key)
    column = columns.get(field_key) or (
        definition.label if definition is not None else field_key
    )
    return RowProblem(
        row_number=outcome.row_number,
        column=column,
        field=field_key,
        value=(outcome.payload or {}).get(field_key),
        code=CODE_CONVERSION_FAILED,
        message=message.format(row=outcome.row_number, reason=failure.reason),
        how_to_fix=how_to_fix,
    )


# ---------------------------------------------------------------------------
# Existing accounts and contacts of the batch
# ---------------------------------------------------------------------------

class _Lookup:
    """Accounts and contacts a row may reuse: the ones already in the database
    for this batch's names / emails / phones, plus the ones created by earlier
    rows of this batch. The oldest record wins a tie."""

    def __init__(self):
        self.accounts_by_name: dict[str, object] = {}
        self.accounts_by_site: dict[str, object] = {}
        self.contacts_by_email: dict[str, object] = {}
        self.contacts_by_phone: dict[str, object] = {}

    @classmethod
    def load(cls, outcomes, context: ConversionContext) -> "_Lookup":
        lookup = cls()
        options = context.options

        if options.account_match == USE_EXISTING:
            names, sites = set(), set()
            for outcome in outcomes:
                data = outcome.payload or {}
                if has_company_name(data.get("company_name")):
                    names.add(_clean_key(data.get("company_name")))
                    sites.add(_clean_key(data.get("website")))
            names.discard(None)
            sites.discard(None)
            if names or sites:
                for account in context.account_repository.find_for_import_matching(
                    names, sites
                ):
                    lookup.remember_account(account)

        if options.contact_match == USE_EXISTING:
            emails, endings = set(), set()
            for outcome in outcomes:
                data = outcome.payload or {}
                emails.add(_clean_key(data.get("email")))
                for key in (
                    phone_key(data.get("phone")),
                    phone_key(data.get("mobile_number")),
                ):
                    if key:
                        endings.add(key[-_PHONE_ENDING_DIGITS:])
            emails.discard(None)
            if emails or endings:
                for contact in context.contact_repository.find_for_import_matching(
                    emails, endings
                ):
                    lookup.remember_contact(contact)
        return lookup

    # -- remembering ----------------------------------------------------

    def remember_account(self, account) -> None:
        name = _clean_key(account.account_name)
        if name:
            self.accounts_by_name.setdefault(name, account)
        site = _clean_key(account.website)
        if site:
            self.accounts_by_site.setdefault(site, account)

    def remember_contact(self, contact) -> None:
        email = _clean_key(contact.email)
        if email:
            self.contacts_by_email.setdefault(email, contact)
        for value in (contact.phone, contact.mobile):
            key = phone_key(value)
            if key:
                self.contacts_by_phone.setdefault(key, contact)

    def replace_contact(self, contact) -> None:
        """A reused contact changed (it got an account): keep the new state."""
        for mapping in (self.contacts_by_email, self.contacts_by_phone):
            for key, stored in list(mapping.items()):
                if stored.id == contact.id:
                    mapping[key] = contact

    # -- finding --------------------------------------------------------

    def account_for(self, lead):
        """Same company name (trimmed, any case), else the same website."""
        name = _clean_key(lead.company_name)
        found = self.accounts_by_name.get(name) if name else None
        if found is None:
            site = _clean_key(lead.website)
            found = self.accounts_by_site.get(site) if site else None
        return found

    def contact_for(self, lead):
        """Same email first, then the same phone (last 10 digits)."""
        email = _clean_key(lead.email)
        found = self.contacts_by_email.get(email) if email else None
        if found is None:
            for value in (lead.mobile_number, lead.phone):
                key = phone_key(value)
                if key and key in self.contacts_by_phone:
                    return self.contacts_by_phone[key]
        return found


# ---------------------------------------------------------------------------
# One row
# ---------------------------------------------------------------------------

@dataclass
class _RowRecord:
    lead_id: UUID
    account: object | None = None
    account_created: bool = False
    contact: object | None = None
    contact_created: bool = False
    contact_changed: bool = False  # a reused contact was attached to the account


def _check_new_row(outcome: RowOutcome) -> None:
    """Existing leads are never converted. The pipeline only marks NEW rows
    (ready / create-anyway) as CONVERT; anything else is a bug."""
    if outcome.status != CONVERT or not outcome.is_converted:
        raise ConversionInternalError(
            f"Row {outcome.row_number} has the status '{outcome.status}' but was "
            "handed to the converter. Only new rows marked as converted can be "
            "converted; an existing lead is never converted by an import."
        )


def _convert_row(job, outcome: RowOutcome, context: ConversionContext, lookup: _Lookup) -> _RowRecord:
    """Runs inside the row's savepoint. Raises ``_RowFailure`` for any problem;
    the caller's savepoint then rolls back everything this function wrote."""
    stage = "lead"
    options = context.options
    actor = context.actor_id
    try:
        lead = context.build_lead(outcome)
        if lead is None:
            raise ValueError("no owner could be assigned to this row")
        context.lead_repository.bulk_create_for_import([lead], job.id)
        record = _RowRecord(lead_id=lead.id)

        stage = "account"
        if has_company_name(lead.company_name):
            found = lookup.account_for(lead) if options.account_match == USE_EXISTING else None
            if found is not None:
                record.account = found
            else:
                record.account = context.account_repository.save(
                    build_account_from_lead(lead, actor)
                )
                record.account_created = True

        stage = "contact"
        found = lookup.contact_for(lead) if options.contact_match == USE_EXISTING else None
        if found is not None:
            contact = copy_entity(found)  # the cached original stays untouched
            if link_contact_to_account(contact, record.account):
                contact = context.contact_repository.save(contact)
                record.contact_changed = True
            record.contact = contact
        else:
            record.contact = context.contact_repository.save(
                build_contact_from_lead(
                    lead,
                    record.account.id if record.account is not None else None,
                    actor,
                )
            )
            record.contact_created = True

        stage = "convert"
        lead.convert()
        context.lead_repository.save(lead)
        return record
    except _RowFailure:
        raise
    except Exception as exc:  # noqa: BLE001 - becomes this row's problem
        raise _RowFailure(stage, _reason(exc, outcome.row_number)) from exc


# ---------------------------------------------------------------------------
# One batch
# ---------------------------------------------------------------------------

def convert_outcomes(job, outcomes, context: ConversionContext) -> ConversionResult:
    """Convert a batch's CONVERT outcomes; every row succeeds or fails alone.

    Failed rows come back in ``result.failed`` as the same ``RowOutcome``
    objects, now with status ERROR and one plain-English problem. Raises
    ``ConversionInternalError`` (rolling the batch back) if a row that must not
    be converted was handed in.
    """
    outcomes = list(outcomes)
    result = ConversionResult()
    for outcome in outcomes:
        _check_new_row(outcome)
    if not outcomes:
        return result

    lookup = _Lookup.load(outcomes, context)

    for outcome in outcomes:
        try:
            record = context.transaction_manager.execute(
                lambda current=outcome: _convert_row(job, current, context, lookup)
            )
        except Exception as exc:  # noqa: BLE001 - one row never stops the batch
            failure = exc if isinstance(exc, _RowFailure) else _RowFailure(
                "lead", _reason(exc, outcome.row_number)
            )
            outcome.problems = [_failure_problem(outcome, failure, context.columns)]
            outcome.status = ERROR
            outcome.is_converted = False
            result.failed.append(outcome)
            continue

        # The row is committed to the batch: later rows may now reuse its records.
        result.converted.append(outcome.row_number)
        result.lead_ids.append(str(record.lead_id))
        if record.account is not None:
            if record.account_created:
                lookup.remember_account(record.account)
                result.created_accounts.append(str(record.account.id))
            else:
                result.reused_accounts.append(str(record.account.id))
        if record.contact is not None:
            if record.contact_created:
                lookup.remember_contact(record.contact)
                result.created_contacts.append(str(record.contact.id))
            else:
                if record.contact_changed:
                    lookup.replace_contact(record.contact)
                result.reused_contacts.append(str(record.contact.id))

    _finish_lists(result)
    return result


def _finish_lists(result: ConversionResult) -> None:
    """No repeats, and a record created by this import is never "reused"."""
    result.created_accounts = list(dict.fromkeys(result.created_accounts))
    result.created_contacts = list(dict.fromkeys(result.created_contacts))
    created_accounts = set(result.created_accounts)
    created_contacts = set(result.created_contacts)
    result.reused_accounts = [
        i for i in dict.fromkeys(result.reused_accounts) if i not in created_accounts
    ]
    result.reused_contacts = [
        i for i in dict.fromkeys(result.reused_contacts) if i not in created_contacts
    ]


# ---------------------------------------------------------------------------
# What is stored on the job
# ---------------------------------------------------------------------------

_CONVERTED_KEYS = (
    "accounts_created", "contacts_created", "accounts_reused", "contacts_reused", "leads",
)


def record_conversion(options: dict, result: ConversionResult) -> dict:
    """``options`` with this batch's records added; the input is not changed.

    ``options["converted"]`` = ``{accounts_created, contacts_created,
    accounts_reused, contacts_reused, leads}`` (ids only, each list capped at
    ``MAX_TRACKED_IDS``; ``truncated`` becomes true when a cap was hit) and
    ``options["counts"]["converted"]`` = rows converted so far.
    """
    updated = dict(options)

    previous = updated.get("converted") if isinstance(updated.get("converted"), dict) else {}
    converted = {key: list(previous.get(key) or []) for key in _CONVERTED_KEYS}
    truncated = bool(previous.get("truncated"))
    additions = {
        "accounts_created": result.created_accounts,
        "contacts_created": result.created_contacts,
        "accounts_reused": result.reused_accounts,
        "contacts_reused": result.reused_contacts,
        "leads": result.lead_ids,
    }
    for key, new_ids in additions.items():
        known = set(converted[key])
        for item in new_ids:
            if item in known:
                continue
            if len(converted[key]) >= MAX_TRACKED_IDS:
                truncated = True
                break
            converted[key].append(item)
            known.add(item)
    converted["truncated"] = truncated
    updated["converted"] = converted

    counts = dict(updated.get("counts")) if isinstance(updated.get("counts"), dict) else {}
    counts["converted"] = int(counts.get("converted") or 0) + len(result.converted)
    updated["counts"] = counts
    return updated


def converted_count(options: dict | None) -> int:
    """Rows converted so far, read from ``options["counts"]["converted"]``."""
    if not isinstance(options, dict):
        return 0
    counts = options.get("counts")
    if isinstance(counts, dict):
        return int(counts.get("converted") or 0)
    return 0
