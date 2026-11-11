from django.urls import path

from .views import LogEmailComposeView

urlpatterns = [
    path(
        "compose/",
        LogEmailComposeView.as_view(),
        name="email-activity-compose",
    ),
]
