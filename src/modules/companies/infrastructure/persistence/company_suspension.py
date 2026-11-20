from uuid import UUID

from src.modules.shared.infrastructure.caching import auth_cache

from .django_company_model import DjangoCompanyModel

SUSPENDED_MESSAGE = "Your company account is suspended."


def is_company_suspended(company_id: UUID | None) -> bool:
    """True when the company exists and is SUSPENDED.

    ONBOARDING and ACTIVE companies are allowed. The answer is cached for
    ``AUTH_CACHE_TTL_SECONDS`` seconds (and cleared as soon as the company is
    saved, see ``company_cache_invalidation.py``); on a miss it is one cheap
    query.
    """
    if company_id is None:
        return False

    key = auth_cache.company_suspension_key(company_id)
    cached = auth_cache.get(key)
    if cached is not None:
        return bool(cached)

    suspended = DjangoCompanyModel.objects.filter(
        id=company_id,
        status=DjangoCompanyModel.Status.SUSPENDED,
    ).exists()
    auth_cache.store(key, suspended)
    return suspended


def is_request_company_suspended(request, company_id: UUID | None) -> bool:
    """``is_company_suspended`` evaluated at most once per request.

    The permission class and the tenant context both need the answer; the
    result is remembered on the request so it is looked up once, not twice.
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
