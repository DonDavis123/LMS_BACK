from django.urls import path

from .views.block_user import BlockUserView
from .views.create_user import CreateUserView
from .views.get_current_user import GetCurrentUserView
from .views.lead_owner import GetLeadOwnersView
from .views.unblock_user import UnblockUserView
from .views.user_detail import UserDetailView


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
        "users/<uuid:user_id>/",
        UserDetailView.as_view(),
        name="user-detail",
    ),
    path(
        "users/<uuid:user_id>/block/",
        BlockUserView.as_view(),
        name="block-user",
    ),
    path(
        "users/<uuid:user_id>/unblock/",
        UnblockUserView.as_view(),
        name="unblock-user",
    ),
    path(
        "lead-owners/",
        GetLeadOwnersView.as_view(),
        name="lead-owners",
    ),
]
