# Rate limiting

Throttling is opt-in per view (`throttle_classes`); `settings.py` still has no
`DEFAULT_THROTTLE_CLASSES`. Rates are `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`
and can be changed with the environment variables below. Counters live in
Django's default cache: Redis with `REDIS_URL` (limits are global across
workers), otherwise per process.

Over the limit the API answers `429` in the usual error shape, with a
`Retry-After` header (seconds):

```json
{ "detail": "Too many requests. Please try again in about 12 minutes." }
```

Code: `src/modules/shared/presentation/throttles.py` (the public lead form keeps
its own throttle in `lead_capture/presentation/api/throttles.py`).

## What is limited

| Endpoint | Keyed by | Scope (env var) | Default |
|---|---|---|---|
| `POST /api/auth/login/` | client IP | `auth_login_ip` (`AUTH_LOGIN_IP_RATE`) | 100/hour |
| | submitted email | `auth_login_email` (`AUTH_LOGIN_EMAIL_RATE`) | 10/hour |
| `POST /api/auth/forgot-password/` | client IP | `auth_forgot_password_ip` (`AUTH_FORGOT_PASSWORD_IP_RATE`) | 10/hour |
| | submitted email | `auth_forgot_password_email` (`AUTH_FORGOT_PASSWORD_EMAIL_RATE`) | 3/hour |
| `POST /api/auth/reset-password/` | client IP | `auth_reset_password_ip` (`AUTH_RESET_PASSWORD_IP_RATE`) | 20/hour |
| `POST` lead / contact / account `.../summary/` and `POST /api/dashboard/briefing/` | user | `ai_generation_user` (`AI_GENERATION_USER_RATE`) | 30/hour |
| | company | `ai_generation_company` (`AI_GENERATION_COMPANY_RATE`) | 300/hour |
| `POST /api/calls/<id>/recordings/<id>/transcript/` | user | `ai_transcription_user` (`AI_TRANSCRIPTION_USER_RATE`) | 10/hour |
| | company | `ai_transcription_company` (`AI_TRANSCRIPTION_COMPANY_RATE`) | 60/hour |
| Public lead form | client IP | `lead_capture_submit` / `lead_capture_view` | 10/hour, 120/hour |

Notes:

- Both limits of a pair apply; the stricter one wins. Per-email limits stop an
  attack on one account from many IPs, per-IP limits stop one machine trying
  many accounts.
- The email is the address *submitted* (trimmed, case-insensitive), whether or
  not an account exists, so a `429` never reveals which emails are registered.
- Every attempt counts, successful or not. A person who is locked out by the
  per-email login limit can still use "Forgot password".
- Only `POST` is counted. `GET` on the summary and transcript URLs never calls
  Gemini (the transcript page polls it), so reads are free.
- Summaries and the daily briefing share one bucket; transcription has its own
  because audio is the most expensive request.
- Rates are `<count>/<second|minute|hour|day>`; an empty variable uses the default.
- These throttles **fail open**: if the cache is unreachable the request is
  allowed and a warning is logged, so a Redis outage cannot block login.
- Behind a reverse proxy set `NUM_PROXIES` to the exact proxy count. Without it
  the client IP cannot be trusted (and a shared proxy address would put every
  user in the same per-IP bucket).
- While `manage.py test` runs, the auth and Gemini limits are effectively off
  (`100000/hour`); `shared/tests/test_throttles.py` sets its own with
  `override_settings`.
