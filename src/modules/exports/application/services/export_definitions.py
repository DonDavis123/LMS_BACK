"""What each exportable list contains: the columns, in order.

Every getter reads one row exactly as the matching list use case returns it,
so an export always shows the same data as the list on screen. Pure Python
apart from the time zone conversion of date-times.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable


@dataclass(frozen=True)
class ExportColumn:
    header: str
    getter: Callable[[Any], Any]


@dataclass(frozen=True)
class ExportDefinition:
    key: str                      # the URL name: /api/exports/<key>/
    file_prefix: str              # start of the downloaded file name
    sheet_title: str
    columns: tuple[ExportColumn, ...]
    supports_filters: bool = True


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------

def datetime_text(value) -> str:
    """``2026-11-02 14:30`` in the project's time zone (empty when unset)."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            from django.utils import timezone

            value = timezone.localtime(value)
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def date_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value)


def label(value) -> str:
    """``IN_PROGRESS`` / enum -> ``In Progress``."""
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return str(raw).replace("_", " ").strip().title()


def names(values) -> str:
    return ", ".join(str(v) for v in (values or ()) if v)


def _col(header: str, getter: Callable[[Any], Any]) -> ExportColumn:
    return ExportColumn(header, getter)


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------

LEADS = ExportDefinition(
    key="leads",
    file_prefix="leads",
    sheet_title="Leads",
    columns=(
        _col("Name", lambda r: r.name),
        _col("Company", lambda r: r.company_name),
        _col("Email", lambda r: r.email),
        _col("Phone", lambda r: r.phone),
        _col("Mobile", lambda r: r.mobile_number),
        _col("Lead Source", lambda r: r.lead_source),
        _col("Lead Status", lambda r: r.lead_status),
        _col("Owner", lambda r: r.owner.name),
        _col("Created At", lambda r: datetime_text(r.created_at)),
        _col("Updated At", lambda r: datetime_text(r.updated_at)),
    ),
)

ACCOUNTS = ExportDefinition(
    key="accounts",
    file_prefix="accounts",
    sheet_title="Accounts",
    columns=(
        _col("Account Name", lambda r: r.account_name),
        _col("Account Number", lambda r: r.account_number),
        _col("Account Type", lambda r: r.account_type),
        _col("Industry", lambda r: r.industry),
        _col("Phone", lambda r: r.phone),
        _col("Website", lambda r: r.website),
        _col("Rating", lambda r: r.rating),
        _col("Employees", lambda r: r.employees),
        _col("Annual Revenue", lambda r: r.annual_revenue),
        _col("Billing Address", lambda r: r.billing_address),
        _col("Billing City", lambda r: r.billing_city),
        _col("Billing State", lambda r: r.billing_state),
        _col("Billing Country", lambda r: r.billing_country),
        _col("Billing Postal Code", lambda r: r.billing_postal_code),
        _col("Owner", lambda r: r.account_owner_name),
        _col("Created At", lambda r: datetime_text(r.created_at)),
        _col("Updated At", lambda r: datetime_text(r.updated_at)),
    ),
)

CONTACTS = ExportDefinition(
    key="contacts",
    file_prefix="contacts",
    sheet_title="Contacts",
    columns=(
        _col("Name", lambda r: r["name"]),
        _col("Title", lambda r: r["title"]),
        _col("Department", lambda r: r["department"]),
        _col("Email", lambda r: r["email"]),
        _col("Secondary Email", lambda r: r["secondary_email"]),
        _col("Phone", lambda r: r["phone"]),
        _col("Mobile", lambda r: r["mobile"]),
        _col("Account", lambda r: r["account_name"]),
        _col("Lead Source", lambda r: r["lead_source"]),
        _col("Owner", lambda r: r["contact_owner_name"]),
        _col("Date of Birth", lambda r: date_text(r["date_of_birth"])),
        _col("Email Opt Out", lambda r: r["email_opt_out"]),
        _col("Mailing Address", lambda r: r["mailing_address"]),
        _col("Mailing City", lambda r: r["mailing_city"]),
        _col("Mailing State", lambda r: r["mailing_state"]),
        _col("Mailing Country", lambda r: r["mailing_country"]),
        _col("Mailing Postal Code", lambda r: r["mailing_postal_code"]),
        _col("Next Task Due Date", lambda r: date_text(r["next_task_due_date"])),
        _col("Next Task Status", lambda r: label(r["next_task_status"])),
        _col("Created At", lambda r: datetime_text(r["created_at"])),
        _col("Updated At", lambda r: datetime_text(r["updated_at"])),
    ),
)

TASKS = ExportDefinition(
    key="tasks",
    file_prefix="tasks",
    sheet_title="Tasks",
    columns=(
        _col("Subject", lambda r: r.task.subject),
        _col("Status", lambda r: label(r.task.status)),
        _col("Priority", lambda r: label(r.task.priority)),
        _col("Due Date", lambda r: date_text(r.task.due_date)),
        _col("Owner", lambda r: r.owner_name),
        _col("Assigned To", lambda r: r.assigned_to_name),
        _col("Lead", lambda r: r.lead_name),
        _col("Contact", lambda r: r.contact_name),
        _col("Account", lambda r: r.account_name),
        _col("Reminder At", lambda r: datetime_text(r.task.reminder_at)),
        _col("Description", lambda r: r.task.description),
        _col("Created At", lambda r: datetime_text(r.task.created_at)),
        _col("Updated At", lambda r: datetime_text(r.task.updated_at)),
    ),
)

CALLS = ExportDefinition(
    key="calls",
    file_prefix="calls",
    sheet_title="Calls",
    columns=(
        _col("Call Start Time", lambda r: datetime_text(r.call.call_start_time)),
        _col("Call Type", lambda r: label(r.call.call_type)),
        _col("Outcome", lambda r: label(r.call.outcome)),
        _col("Duration", lambda r: r.call.duration_label),
        _col("Duration (seconds)", lambda r: r.call.duration_seconds),
        _col("Owner", lambda r: r.owner_name),
        _col("Lead", lambda r: r.lead_name),
        _col("Contact", lambda r: r.contact_name),
        _col("Account", lambda r: r.account_name),
        _col("Entry Method", lambda r: label(r.call.entry_method)),
        _col("Description", lambda r: r.call.description),
        _col("Created At", lambda r: datetime_text(r.call.created_at)),
    ),
)

MEETINGS = ExportDefinition(
    key="meetings",
    file_prefix="meetings",
    sheet_title="Meetings",
    supports_filters=False,  # the meetings list does not support filters
    columns=(
        _col("Title", lambda r: r.title),
        _col("Start", lambda r: datetime_text(r.start_at)),
        _col("End", lambda r: datetime_text(r.end_at)),
        _col("Reminder At", lambda r: datetime_text(r.reminder_at)),
        _col("Host", lambda r: r.host_name),
        _col("Related To Type", lambda r: label(r.related_to_type)),
        _col("Related To", lambda r: names(r.related_to_names)),
        _col("Contacts", lambda r: names(r.contact_names)),
    ),
)

DEFINITIONS: dict[str, ExportDefinition] = {
    definition.key: definition
    for definition in (LEADS, ACCOUNTS, CONTACTS, TASKS, CALLS, MEETINGS)
}
