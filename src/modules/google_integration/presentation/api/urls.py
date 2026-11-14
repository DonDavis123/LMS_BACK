from django.urls import path

from .views.google_connection import (
    GoogleConnectCallbackView,
    GoogleConnectionStatusView,
    GoogleConnectStartView,
    GoogleDisconnectView,
)


urlpatterns = [
    path("status/", GoogleConnectionStatusView.as_view(), name="google-status"),
    path("connect/", GoogleConnectStartView.as_view(), name="google-connect"),
    path("callback/", GoogleConnectCallbackView.as_view(), name="google-callback"),
    path("disconnect/", GoogleDisconnectView.as_view(), name="google-disconnect"),
]
