# Redis cache

The default Django cache is Redis when `REDIS_URL` is set, and Django's
in-memory cache otherwise (local development, tests). Nothing else in the
architecture changes.

## Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `REDIS_URL` | empty | e.g. `redis://:password@host:6379/0`, or `rediss://...` for TLS. Empty = in-memory cache. |
| `CACHE_KEY_PREFIX` | `lms` | Prefix for every key, so environments can share one Redis. |
| `REDIS_CONNECT_TIMEOUT` / `REDIS_SOCKET_TIMEOUT` | `0.5` | Seconds before a Redis call gives up. |
| `AUTH_CACHE_TTL_SECONDS` | `60` | How long the user row and the company-suspension answer are cached. `0` turns it off. |

## What is cached

Every authenticated request used to run two queries before any business logic:

1. the JWT user lookup -> `CachedJWTAuthentication`
   (`authentication/infrastructure/security/cached_jwt_authentication.py`)
2. the company-suspension check -> `is_company_suspended`
   (`companies/infrastructure/persistence/company_suspension.py`)

Both now read from the cache first. Helpers live in
`shared/infrastructure/caching/auth_cache.py`.

## Invalidation

Saving or deleting a user (role change, block/unblock, soft delete, password
reset, profile edit) or a company (suspend / reactivate) clears its entry
immediately through `post_save` / `post_delete` signals, and again after the
transaction commits. A suspension therefore applies on the next request, not
after the TTL. Only a bulk `QuerySet.update()` (no signal) or raw SQL can leave a
stale entry, for at most `AUTH_CACHE_TTL_SECONDS`.

## Failure behaviour

The auth cache fails open: if Redis is down or slow, reads count as a miss and
the request uses the database, exactly as before. Note that the lead-capture
throttles also use this cache; DRF throttling does not fail open, so a Redis
outage can make those public endpoints error until Redis is back.
