from uuid import UUID

from .django_company_model import DjangoCompanyModel

SUSPENDED_MESSAGE = "Your company account is suspended."


def is_company_suspended(company_id: UUID | None) -> bool:
    """True when the company exists and is SUSPENDED (one cheap query).

    ONBOARDING and ACTIVE companies are allowed.
    """
    if company_id is None:
        return False

    return DjangoCompanyModel.objects.filter(
        id=company_id,
        status=DjangoCompanyModel.Status.SUSPENDED,
    ).exists()
