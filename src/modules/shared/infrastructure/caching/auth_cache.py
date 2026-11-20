"""Short-lived cache for the two lookups every authenticated request makes.

* the user row read by the JWT authentication class, and
* the "is this company suspended?" check made by ``IsCompanyUser`` and the
  tenant context.

Both are stored in Django's default cache (Redis when ``REDIS_URL`` is set,
see ``config/settings.py``) for ``AUTH_CACHE_TTL_SECONDS`` seconds. Writes to
the user / company rows delete the entries right away (see the
``*_cache_invalidation`` signal modules), so the TTL is only a safety net.

The cache is an optimisation, never a dependency: every helper swallows cache
errors (for example Redis being down) and behaves as a miss, so the request
falls back to the database. ``AUTH_CACHE_TTL_SECONDS = 0`` switches it off.
"""

import logging
from typing import Any
from uuid import UUID

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger(__name__)

_MISSING = object()


def _ttl() -> int:
    return int(getattr(settings, "AUTH_CACHE_TTL_SECONDS", 0) or 0)


def is_enabled() -> bool:
    return _ttl() > 0


def user_key(user_id: Any) -> str:
    return f"auth:user:{user_id}"


def company_suspension_key(company_id: UUID) -> str:
    return f"auth:company-suspended:{company_id}"


def get(key: str, default: Any = None) -> Any:
    """Cached value, or ``default`` on a miss, a disabled cache or an error."""
    if not is_enabled():
        return default
    try:
        value = cache.get(key, _MISSING)
    except Exception:
        logger.warning("Auth cache read failed for %s", key, exc_info=True)
        return default
    return default if value is _MISSING else value


def store(key: str, value: Any) -> None:
    if not is_enabled():
        return
    try:
        cache.set(key, value, _ttl())
    except Exception:
        logger.warning("Auth cache write failed for %s", key, exc_info=True)


def delete(key: str) -> None:
    """Delete now and again after the surrounding transaction commits.

    The second delete closes a race: a concurrent request could read the old
    row before the commit and store it in the cache just after the first
    delete. The cache is cleared even when the cache is disabled in settings
    (cheap, and keeps a later re-enable safe).
    """
    _delete_now(key)
    try:
        transaction.on_commit(lambda: _delete_now(key))
    except Exception:
        logger.warning("Could not schedule auth cache delete for %s", key, exc_info=True)


def _delete_now(key: str) -> None:
    try:
        cache.delete(key)
    except Exception:
        logger.warning("Auth cache delete failed for %s", key, exc_info=True)
