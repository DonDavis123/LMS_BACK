from django.urls import path

from .views.login import LoginView
from .views.refresh_tokens import RefreshTokenView


urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshTokenView.as_view(), name="refresh-token"),
]