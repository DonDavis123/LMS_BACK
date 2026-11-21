"""Version-keyed cache for the ``COUNT(*)`` behind every paginated list.

Only the integer ``total`` is cached, never the rows. Two kinds of keys live in
Django's default cache (Redis when ``REDIS_URL`` is set, see
``config/settings.py``):

* ``ver:{company_id}:{resource}`` - an integer counter, the "version" of one
  company's list of one resource;
* ``count:{company_id}:{resource}:v{version}:{filter_hash}`` - the cached
  total, stored for ``COUNT_CACHE_TTL_SECONDS``.

A list request reads the version, looks up the count key and, on a miss, runs
the real ``COUNT(*)`` and stores it. Any write to the resource increments the
version (see :func:`bump_version` and the ``count_cache_invalidation`` signal
modules), so every older count key becomes unreachable at once; the TTL only
cleans them up. Every key starts with the company id, so two companies never
share an entry.

Like ``auth_cache`` the cache is an optimisation, never a dependency: cache
errors (for example Redis being down) are logged and behave as a miss, so the
request falls back to the database. Errors raised by ``count_fn`` itself are
real database errors and are NOT swallowed. ``COUNT_CACHE_TTL_SECONDS = 0``
switches the cache off.
"""

import hashlib
import json
import logging
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any
from uuid import UUID

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction

logger = logging.getLogger(__name__)

LEADS = "leads"
CONTACTS = "contacts"
DEALS = "deals"
TASKS = "tasks"
ACCOUNTS = "accounts"
CALLS = "calls"
USERS = "users"

# A write to the key resource can change the total of every resource in the
# value. Besides its own list, a resource shows up in other lists through
# filters / search on related records, for example:
#   * leads: the ``account_name`` / ``contact_name`` filters look at accounts
#     and contacts;
#   * contacts: the ``account_name`` / ``contact_owner_name`` filters;
#   * tasks: ``contact_name`` and ``related_to`` (lead, contact, account names);
#   * calls: search and ``record_name`` / ``account_name`` filters, and the
#     owner's name in the search.
_AFFECTS: dict[str, tuple[str, ...]] = {
    LEADS: (LEADS, TASKS, CALLS),
    CONTACTS: (CONTACTS, LEADS, TASKS, CALLS),
    ACCOUNTS: (ACCOUNTS, CONTACTS, LEADS, TASKS, CALLS),
    DEALS: (DEALS,),
    TASKS: (TASKS,),
    CALLS: (CALLS,),
    # A user's name is searched / filtered as the owner's name.
    USERS: (CONTACTS, CALLS),
}


def _ttl() -> int:
    return max(0, int(getattr(settings, "COUNT_CACHE_TTL_SECONDS", 0) or 0))


def is_enabled() -> bool:
    return _ttl() > 0


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

def version_key(company_id: UUID | str, resource: str) -> str:
    return f"ver:{company_id}:{resource}"


def count_key(
    company_id: UUID | str, resource: str, version: int, hash_: str
) -> str:
    return f"count:{company_id}:{resource}:v{version}:{hash_}"


def _canonical(value: Any) -> Any:
    """A JSON-friendly copy of ``value`` that does not depend on ordering."""
    if isinstance(value, Mapping):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda i: str(i[0]))}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_canonical(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    if isinstance(value, str):
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)  # UUID, date, datetime, Decimal, enums...


def _condition_parts(condition: Any) -> dict[str, Any]:
    """One ``FilterCondition`` (or a plain mapping) as a comparable dict."""
    if isinstance(condition, Mapping):
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")
    else:
        field = getattr(condition, "field", None)
        operator = getattr(condition, "operator", None)
        value = getattr(condition, "value", None)
    return {
        "field": str(field or "").strip(),
        "operator": str(operator or "").strip(),
        "value": _canonical(value),
    }


def build_filter_parts(
    search: str | None = None,
    filters: Iterable[Any] = (),
    **extra: Any,
) -> dict[str, Any]:
    """Everything that changes which rows a list counts, except paging/sorting.

    ``search`` and ``filters`` come from the ``ListQuery``. ``extra`` holds
    what the repository adds on its own: fixed filters (``is_deleted=False``,
    ``is_converted=False``), the variant of the list (``variant="records"``)
    and any per-user scope. Sort order, ``page`` and ``page_size`` must never
    be passed in: they do not change the total.
    """
    return {
        "search": (search or "").strip(),
        "filters": list(filters or ()),
        "extra": extra,
    }


def filter_hash(parts: Mapping[str, Any]) -> str:
    """Stable sha1 of the search text, all filters and the extra parts.

    Filters are ANDed, so their order is irrelevant: they are normalised
    (field / operator trimmed, list values sorted) and then sorted.
    """
    normalised = {
        "search": str(parts.get("search") or "").strip(),
        "filters": sorted(
            (
                _condition_parts(condition)
                for condition in (parts.get("filters") or ())
            ),
            key=lambda item: json.dumps(item, sort_keys=True, default=str),
        ),
        "extra": _canonical(parts.get("extra") or {}),
    }
    payload = json.dumps(
        normalised, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Version counter
# ---------------------------------------------------------------------------

def _seed() -> int:
    # A missing version (first use, or Redis evicted it) starts at the current
    # time in microseconds rather than 0. Count keys written under an earlier
    # life of the counter can therefore never be hit again.
    return time.time_ns() // 1000


def _read_version(company_id: UUID | str, resource: str) -> int:
    key = version_key(company_id, resource)
    version = cache.get(key)
    if version is None:
        cache.add(key, _seed(), None)  # no-op if another worker won the race
        version = cache.get(key)
    return int(version)


def bump_version(company_id: UUID | str | None, resource: str) -> None:
    """Make every cached total of ``resource`` for this company unreachable.

    Never raises. Called after any write, including the ones that send no
    signal (``bulk_create``, ``bulk_update``, ``QuerySet.update()``).

    Inside a transaction the version is bumped now and once more after the
    commit. The second bump closes a race: a request that runs between the
    first bump and the commit would read the old rows, and cache that total
    under the new version. It is bumped even when the cache is switched off,
    so a later re-enable never meets a stale entry.
    """
    if company_id is None:
        return
    _bump_now(company_id, resource)
    try:
        if connection.in_atomic_block:
            transaction.on_commit(lambda: _bump_now(company_id, resource))
    except Exception:
        logger.warning(
            "Could not schedule count cache bump for %s/%s",
            company_id, resource, exc_info=True,
        )


def bump_affected(company_id: UUID | str | None, source: str) -> None:
    """Bump ``source`` and every other list that shows it (see ``_AFFECTS``)."""
    for resource in _AFFECTS.get(source, (source,)):
        bump_version(company_id, resource)


def _bump_now(company_id: UUID | str, resource: str) -> None:
    key = version_key(company_id, resource)
    try:
        try:
            cache.incr(key)
        except ValueError:  # no counter yet
            cache.add(key, _seed(), None)
    except Exception:
        logger.warning("Count cache bump failed for %s", key, exc_info=True)


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

def get_or_count(
    company_id: UUID | str | None,
    resource: str,
    filter_parts: Mapping[str, Any],
    count_fn: Callable[[], int],
) -> int:
    """The list total: from the cache when possible, else ``count_fn()``.

    ``filter_parts`` is built with :func:`build_filter_parts` and must describe every
    condition ``count_fn`` applies. Cache failures never raise: they are logged
    and the total comes from ``count_fn()``.
    """
    ttl = _ttl()
    if ttl <= 0 or company_id is None:
        return count_fn()

    try:
        key = count_key(
            company_id,
            resource,
            _read_version(company_id, resource),
            filter_hash(filter_parts),
        )
        cached = cache.get(key)
    except Exception:
        logger.warning(
            "Count cache read failed for %s/%s", company_id, resource, exc_info=True
        )
        return count_fn()

    if isinstance(cached, int) and not isinstance(cached, bool) and cached >= 0:
        return cached

    total = count_fn()
    try:
        cache.set(key, int(total), ttl)
    except Exception:
        logger.warning("Count cache write failed for %s", key, exc_info=True)
    return total
