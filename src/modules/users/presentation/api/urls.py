from django.urls import path

from .views.create_user import CreateUserView
from .views.get_current_user import GetCurrentUserView


urlpatterns = [
    path(
        "users/",
        CreateUserView.as_view(),
        name="create-user",
    ),
    path(
        "users/me/",
        GetCurrentUserView.as_view(),
        name="current-user",
    ),
]