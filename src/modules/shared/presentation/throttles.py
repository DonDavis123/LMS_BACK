"""Rate limits for the endpoints that are cheap to abuse.

Two groups, both opted in per view with ``throttle_classes`` (there is still no
``DEFAULT_THROTTLE_CLASSES``, so every other endpoint stays unthrottled):

* Authentication (anonymous callers, keyed by client IP and by submitted email)
    - ``LoginIPThrottle`` / ``LoginEmailThrottle``: brute force and credential
      stuffing.
    - ``ForgotPasswordIPThrottle`` / ``ForgotPasswordEmailThrottle``: mail
      spam. The email key is the *submitted* address whether or not an account
      exists, so a 429 never reveals which emails are registered.
    - ``ResetPasswordThrottle``: reset-token guessing.

* Gemini-backed endpoints (authenticated callers, keyed by user and by company)
    - ``AIGenerationUserThrottle`` / ``AIGenerationCompanyThrottle``: the lead,
      contact and account summaries and the daily briefing share one bucket.
    - ``TranscriptionUserThrottle`` / ``TranscriptionCompanyThrottle``: call
      recording transcription (audio is far more expensive, so its own bucket).
    The per-company limit caps what one tenant can spend of the shared Gemini
    quota; the per-user limit stops a single account (or leaked token) from
    using the whole company allowance.

Only ``POST`` is counted. ``GET`` on the same URLs never calls the model (and
the transcript page polls it), so reads are not limited.

Rates come from ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`` (see
``config/settings.py``) and are read on every request, so ``override_settings``
works in tests. Counters live in Django's default cache: Redis when
``REDIS_URL`` is set (limits are then global across workers), otherwise a
per-process cache. Client IPs honour ``REST_FRAMEWORK["NUM_PROXIES"]``.

Unlike DRF's stock throttles these **fail open**: if the cache is unreachable
(Redis down) the request is allowed and a warning is logged, so a cache outage
can never lock people out of login or the app. This mirrors the auth cache.
"""

import hashlib
import logging

from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle

logger = logging.getLogger(__name__)

_MAX_EMAIL_LENGTH = 254


class _PostThrottle(SimpleRateThrottle):
    """Base: counts POST requests only, rate looked up lazily, fails open."""

    methods = ("POST",)

    def get_rate(self):
        # A scope missing from the settings means "not limited".
        return api_settings.DEFAULT_THROTTLE_RATES.get(self.scope)

    def allow_request(self, request, view):
        if request.method not in self.methods:
            return True
        try:
            return super().allow_request(request, view)
        except Exception:
            logger.warning(
                "Throttle %s failed (cache unavailable?); allowing the request.",
                self.scope,
                exc_info=True,
            )
            return True

    def _key(self, ident) -> str:
        return self.cache_format % {"scope": self.scope, "ident": ident}


class _IPThrottle(_PostThrottle):
    def get_cache_key(self, request, view):
        return self._key(self.get_ident(request))


class _SubmittedEmailThrottle(_PostThrottle):
    """Keyed by the ``email`` in the request body, case-insensitively.

    The address is hashed, so the cache key is always short and safe whatever
    the caller sends. A body without a usable email is not counted here (the
    per-IP throttle on the same view still applies).
    """

    def get_cache_key(self, request, view):
        data = request.data
        email = data.get("email") if hasattr(data, "get") else None
        if not isinstance(email, str):
            return None
        email = email.strip().lower()[:_MAX_EMAIL_LENGTH]
        if not email:
            return None
        return self._key(hashlib.sha256(email.encode("utf-8")).hexdigest())


class _UserThrottle(_PostThrottle):
    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None
        return self._key(user.pk)


class _CompanyThrottle(_PostThrottle):
    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        company_id = getattr(user, "company_id", None)
        if company_id is None:
            return None
        return self._key(company_id)


# ---------------------------------------------------------------- authentication


class LoginIPThrottle(_IPThrottle):
    scope = "auth_login_ip"


class LoginEmailThrottle(_SubmittedEmailThrottle):
    scope = "auth_login_email"


class ForgotPasswordIPThrottle(_IPThrottle):
    scope = "auth_forgot_password_ip"


class ForgotPasswordEmailThrottle(_SubmittedEmailThrottle):
    scope = "auth_forgot_password_email"


class ResetPasswordThrottle(_IPThrottle):
    scope = "auth_reset_password_ip"


# ---------------------------------------------------------------------- Gemini


class AIGenerationUserThrottle(_UserThrottle):
    scope = "ai_generation_user"


class AIGenerationCompanyThrottle(_CompanyThrottle):
    scope = "ai_generation_company"


class TranscriptionUserThrottle(_UserThrottle):
    scope = "ai_transcription_user"


class TranscriptionCompanyThrottle(_CompanyThrottle):
    scope = "ai_transcription_company"
