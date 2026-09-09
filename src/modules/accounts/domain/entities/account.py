from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class Account:
    id: UUID
    account_owner_id: UUID
    account_name: str
    account_site: str | None
    account_number: str | None
    account_type: str | None
    industry: str | None
    annual_revenue: int | None
    rating: str | None
    phone: str | None
    website: str | None
    ticker_symbol: str | None
    ownership: str
    employees: int | None
    sic_code: str | None

    # Billing information
    billing_address: str | None
    billing_city: str | None
    billing_state: str | None
    billing_country: str | None
    billing_postal_code: str | None

    # Description
    description: str | None

    # Audit information
    created_by_id: UUID
    created_at: datetime
    modified_by_id: UUID
    updated_at: datetime

    is_deleted: bool

    @classmethod
    def create(
        cls,
        account_owner_id: UUID,
        account_name: str,
        account_site: str | None,
        account_number: str | None,
        account_type: str | None,
        industry: str | None,
        annual_revenue: int | None,
        rating: str | None,
        phone: str | None,
        website: str | None,
        ticker_symbol: str | None,
        ownership: str | None,
        employees: int | None,
        sic_code: str | None,
        billing_address: str | None,
        billing_city: str | None,
        billing_state: str | None,
        billing_country: str | None,
        billing_postal_code: str | None,
        description: str | None,
        created_by_id: UUID,
    ) -> "Account":

        now = datetime.utcnow()

        return cls(
            id=uuid4(),
            account_owner_id=account_owner_id,
            account_name=account_name,
            account_site=account_site,
            account_number=account_number,
            account_type=account_type,
            industry=industry,
            annual_revenue=annual_revenue,
            rating=rating,
            phone=phone,
            website=website,
            ticker_symbol=ticker_symbol,
            ownership=ownership or "None",
            employees=employees,
            sic_code=sic_code,
            billing_address=billing_address,
            billing_city=billing_city,
            billing_state=billing_state,
            billing_country=billing_country,
            billing_postal_code=billing_postal_code,
            description=description,
            created_by_id=created_by_id,
            created_at=now,
            modified_by_id=created_by_id,
            updated_at=now,
            is_deleted=False,
        )