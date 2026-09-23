from django.conf import settings
from django.http import HttpRequest
from django.http import HttpResponse


def _get_cookie_security_options(
    request: HttpRequest,
) -> dict[str, object]:
    """Select refresh-cookie security from the current request scheme.

    Local HTTP:
        Secure=False, SameSite=Lax

    HTTPS (including ngrok):
        Secure=True, SameSite=None
    """

    is_secure = request.is_secure()

    return {
        "secure": is_secure,
        "samesite": "None" if is_secure else "Lax",
    }


def get_refresh_token(request: HttpRequest) -> str | None:
    return request.COOKIES.get(settings.REFRESH_COOKIE_NAME)


def set_refresh_token_cookie(
    request: HttpRequest,
    response: HttpResponse,
    refresh_token: str,
) -> None:
    cookie_security = _get_cookie_security_options(request)

    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=cookie_security["secure"],
        samesite=cookie_security["samesite"],
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
    )


def clear_refresh_token_cookie(
    request: HttpRequest,
    response: HttpResponse,
) -> None:
    cookie_security = _get_cookie_security_options(request)

    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        samesite=cookie_security["samesite"],
    )
