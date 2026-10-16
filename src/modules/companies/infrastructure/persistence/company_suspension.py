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


def is_request_company_suspended(request, company_id: UUID | None) -> bool:
    """``is_company_suspended`` evaluated at most once per request.

    The permission class and the tenant context both need the answer; the
    result is remembered on the request so it costs one query, not two.
    """
    cache = getattr(request, "_company_suspension_cache", None)
    if cache is None:
        cache = {}
        try:
            request._company_suspension_cache = cache
        except AttributeError:
            return is_company_suspended(company_id)
    if company_id not in cache:
        cache[company_id] = is_company_suspended(company_id)
    return cache[company_id]
