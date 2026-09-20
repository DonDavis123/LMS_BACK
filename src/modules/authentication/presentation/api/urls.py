from django.urls import path

from .views.login import LoginView
from .views.refresh_tokens import RefreshTokenView
from .views.logout import LogoutView
from src.modules.authentication.presentation.api.views.forgot_password import (
    ForgotPasswordView,
)
from src.modules.authentication.presentation.api.views.reset_password import (
    ResetPasswordView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshTokenView.as_view(), name="refresh-token"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path(
        "forgot-password/",
        ForgotPasswordView.as_view(),
        name="forgot-password",
    ),
    path(
        "reset-password/",
        ResetPasswordView.as_view(),
        name="reset-password",
    ),
]
