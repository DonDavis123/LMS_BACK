from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle


class PublicLeadFormThrottle(SimpleRateThrottle):
    """Per-client-IP throttle for the public lead form, scope chosen by method.

    POST -> ``lead_capture_submit``, GET -> ``lead_capture_view``. Any other
    method is not throttled. Rates are read from
    ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`` on every request (not at
    import time), so they can be changed with ``override_settings``.
    The client IP honours ``REST_FRAMEWORK["NUM_PROXIES"]``.
    """

    SCOPES = {
        "POST": "lead_capture_submit",
        "GET": "lead_capture_view",
    }

    def __init__(self):
        # The scope depends on the request, so the rate is resolved in
        # allow_request() instead of here.
        pass

    def get_rate(self):
        return api_settings.DEFAULT_THROTTLE_RATES[self.scope]

    def allow_request(self, request, view):
        self.scope = self.SCOPES.get(request.method)
        if self.scope is None:
            return True
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }
