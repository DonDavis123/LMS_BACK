from django.conf import settings
from django.http import HttpRequest
from django.http import HttpResponse


def get_refresh_token(request: HttpRequest) -> str | None:
    return request.COOKIES.get(settings.REFRESH_COOKIE_NAME)


def set_refresh_token_cookie(
    response: HttpResponse,
    refresh_token: str,
) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
    )


def clear_refresh_token_cookie(response: HttpResponse) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )
