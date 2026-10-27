"""Importable lead fields, header aliases and column-mapping suggestions.

Pure Python: no Django models and no database access, so everything here is
easy to unit test.

The field list mirrors ``CreateLeadSerializer`` (the authoritative source for
names, types and maximum lengths). If a limit changes there, change it here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Kinds drive how a cell is cleaned (lead_import_cleaning.py) and validated.
KIND_TEXT = "text"
KIND_EMAIL = "email"
KIND_PHONE = "phone"
KIND_URL = "url"
KIND_INT = "int"
KIND_PICKLIST = "picklist"
KIND_OWNER = "owner"


@dataclass(frozen=True)
class ImportField:
    key: str
    label: str
    required: bool
    max_length: int | None  # None = no limit in CreateLeadSerializer
    kind: str
    aliases: tuple[str, ...] = ()
    # Keep line breaks inside the value (descriptions) instead of collapsing
    # every run of whitespace into one space.
    multiline: bool = False


def normalize_header(text: object) -> str:
    """Lower-case, punctuation-insensitive form used to compare headers.

    "Name of company ? " -> "name of company"; "E-mail" -> "e mail".
    """
    if text is None:
        return ""
    lowered = str(text).lower()
    spaced = re.sub(r"[^0-9a-z]+", " ", lowered)
    return re.sub(r"\s+", " ", spaced).strip()


def _compact(normalized: str) -> str:
    return normalized.replace(" ", "")


# Order here is the order shown on the mapping screen and in the template.
IMPORT_FIELDS: tuple[ImportField, ...] = (
    ImportField(
        "name", "Name", True, 255, KIND_TEXT,
        ("full name", "lead name", "contact name", "customer name", "person name",
         "owner name", "owners name"),
    ),
    ImportField(
        "title", "Title", False, 150, KIND_TEXT,
        ("job title", "designation", "position", "role"),
    ),
    ImportField(
        "company_name", "Company Name", False, 255, KIND_TEXT,
        ("company", "name of company", "organisation", "organization", "account name", "business name"),
    ),
    ImportField(
        "email", "Email", False, 254, KIND_EMAIL,
        ("e-mail", "email address", "mail", "email id", "e mail id"),
    ),
    ImportField(
        "mobile_number", "Mobile Number", False, 20, KIND_PHONE,
        ("mobile", "cell", "cell phone", "mobile no", "mobile phone"),
    ),
    ImportField(
        "phone", "Phone", False, 20, KIND_PHONE,
        ("phone number", "telephone", "tel", "ph no", "contact number", "contact no"),
    ),
    ImportField(
        "lead_source", "Lead Source", False, 100, KIND_PICKLIST,
        ("source", "lead origin"),
    ),
    ImportField(
        "lead_status", "Lead Status", False, 100, KIND_PICKLIST,
        ("status",),
    ),
    ImportField(
        "industry", "Industry", False, 150, KIND_PICKLIST,
        ("sector", "industry type"),
    ),
    ImportField(
        "rating", "Rating", False, 100, KIND_PICKLIST,
        ("lead rating",),
    ),
    ImportField(
        "website", "Website", False, 200, KIND_URL,
        ("web site", "url", "site", "web", "website url"),
    ),
    ImportField(
        "number_of_employees", "Number of Employees", False, None, KIND_INT,
        ("employees", "no of employees", "employee count", "company size", "headcount"),
    ),
    ImportField(
        "annual_revenue", "Annual Revenue", False, None, KIND_INT,
        ("revenue", "annual turnover", "turnover"),
    ),
    ImportField(
        "address", "Address", False, 500, KIND_TEXT,
        ("street", "street address", "address line 1"),
    ),
    ImportField("city", "City", False, 100, KIND_TEXT, ("town",)),
    ImportField("state", "State", False, 100, KIND_TEXT, ("province", "region")),
    ImportField("country", "Country", False, 100, KIND_TEXT, ("nation",)),
    ImportField(
        "postal_code", "Postal Code", False, 20, KIND_TEXT,
        ("zip", "zip code", "pincode", "pin code", "postcode", "postal"),
    ),
    ImportField(
        "description", "Description", False, None, KIND_TEXT,
        ("notes", "note", "remarks", "comments", "about", "details"),
        multiline=True,
    ),
    # Virtual field: not a lead column. It is matched to a CRM user (by email
    # or full name) to decide the lead's owner. Only explicit CRM-owner
    # phrases are aliases, so a plain "Owner" / "Owner name" column (often the
    # business owner) is never mapped to it automatically.
    ImportField(
        "owner", "Owner (email or full name)", False, None, KIND_OWNER,
        ("lead owner", "assigned to", "assigned user", "owner email",
         "sales rep", "sales representative", "crm owner"),
    ),
)

IMPORT_FIELDS_BY_KEY: dict[str, ImportField] = {f.key: f for f in IMPORT_FIELDS}


def get_field(key: str) -> ImportField | None:
    return IMPORT_FIELDS_BY_KEY.get(key)


def _exact_names(field: ImportField) -> set[str]:
    names = {normalize_header(field.key), normalize_header(field.label)}
    return {n for n in names if n}


def _build_lookups() -> tuple[dict[str, str], dict[str, str]]:
    exact: dict[str, str] = {}
    alias: dict[str, str] = {}
    for field in IMPORT_FIELDS:
        for name in _exact_names(field):
            exact.setdefault(name, field.key)
            exact.setdefault(_compact(name), field.key)
        for raw in field.aliases:
            norm = normalize_header(raw)
            if norm:
                alias.setdefault(norm, field.key)
                alias.setdefault(_compact(norm), field.key)
    return exact, alias


_EXACT, _ALIAS = _build_lookups()


def suggest_mapping(headers: list[str]) -> dict[str, str | None]:
    """Suggest a CRM field for each file header.

    Returns ``{header: field_key or None}``. Each field is used at most once
    (the first matching column wins). Exact matches on a field's key or label
    are made before alias matches, so a column literally named "Phone" is not
    stolen by an earlier column that merely has a phone-like alias.
    """
    result: dict[str, str | None] = {header: None for header in headers}
    used: set[str] = set()

    def run(lookup: dict[str, str]) -> None:
        for header in headers:
            if result[header] is not None:
                continue
            norm = normalize_header(header)
            if not norm:
                continue
            key = lookup.get(norm) or lookup.get(_compact(norm))
            if key and key not in used:
                result[header] = key
                used.add(key)

    run(_EXACT)
    run(_ALIAS)
    return result
