from django.urls import path

from .views.create_user import CreateUserView
from .views.get_current_user import GetCurrentUserView
from .views.lead_owner import GetLeadOwnersView


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

     path(
        "lead-owners/",
        GetLeadOwnersView.as_view(),
        name="lead-owners",
    ),
]