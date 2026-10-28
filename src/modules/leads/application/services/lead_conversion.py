"""The rules of "convert a lead", shared by the Convert Lead button and the
lead import, so both produce identical Accounts and Contacts.

``ConvertLeadUseCase`` uses these when it builds an Account / Contact from the
lead itself (no data supplied by the screen) and when it attaches an existing
Contact to an Account. ``lead_import_conversion`` uses the very same
functions. Pure code: no database access, no timeline.
"""

from __future__ import annotations

import copy
from uuid import UUID

from src.modules.accounts.domain.entities.account import Account
from src.modules.contacts.domain.entities.contact import Contact
from src.modules.leads.domain.entities.option_text import option_text


def has_company_name(company_name: str | None) -> bool:
    """A lead without a company converts as a Contact only (no Account)."""
    return bool(company_name and company_name.strip())


def build_account_from_lead(lead, created_by_id: UUID) -> Account:
    """The Account a lead becomes: company, industry, rating, phone, website,
    employees, revenue, address and description. Nothing else is copied."""
    return Account.create(
        account_owner_id=lead.owner_id,
        account_name=lead.company_name,
        account_site=None,
        account_number=None,
        account_type=None,
        industry=option_text(lead.industry),
        annual_revenue=lead.annual_revenue,
        rating=option_text(lead.rating),
        phone=lead.phone,
        website=lead.website,
        ticker_symbol=None,
        ownership="None",
        employees=lead.number_of_employees,
        sic_code=None,
        billing_address=lead.address,
        billing_city=lead.city,
        billing_state=lead.state,
        billing_country=lead.country,
        billing_postal_code=lead.postal_code,
        description=lead.description,
        created_by_id=created_by_id,
    )


def build_contact_from_lead(
    lead,
    account_id: UUID | None,
    created_by_id: UUID,
) -> Contact:
    """The Contact a lead becomes: the person (name, email, phones, title,
    source), the address as the mailing address, and the description."""
    return Contact.create(
        account_id=account_id,
        contact_owner_id=lead.owner_id,
        name=lead.name,
        email=lead.email,
        secondary_email=None,
        phone=lead.phone,
        other_phone=None,
        mobile=lead.mobile_number,
        home_phone=None,
        assistant_phone=None,
        title=lead.title,
        department=None,
        lead_source=option_text(lead.lead_source),
        vendor_name=None,
        date_of_birth=None,
        assistant=None,
        email_opt_out=False,
        reporting_to_id=None,
        mailing_address=lead.address,
        mailing_city=lead.city,
        mailing_state=lead.state,
        mailing_country=lead.country,
        mailing_postal_code=lead.postal_code,
        other_address=None,
        description=lead.description,
        created_by_id=created_by_id,
    )


def link_contact_to_account(contact: Contact, account: Account | None) -> bool:
    """Attach an existing Contact to the conversion's Account.

    Zoho-style rule: a Contact that already has an Account keeps it, and a
    conversion without an Account never attaches one. Returns True when the
    contact was changed (the caller saves it).
    """
    if contact.account_id is not None:
        return False
    if account is None:
        return False
    contact.account_id = account.id
    return True


def copy_entity(entity):
    """A shallow copy, so a row can change a record without touching the cached
    original until the row has succeeded."""
    return copy.copy(entity)
