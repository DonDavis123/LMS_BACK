from django.urls import path

from .views.block_user import BlockUserView
from .views.create_user import CreateUserView
from .views.get_current_user import GetCurrentUserView
from .views.get_user_audit_logs import UserAuditLogListView
from .views.get_user_deletion_preview import UserDeletionPreviewView
from .views.lead_owner import GetLeadOwnersView
from .views.reset_user_password import ResetUserPasswordView
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
        "users/audit-logs/",
        UserAuditLogListView.as_view(),
        name="user-audit-logs",
    ),
    path(
        "users/<uuid:user_id>/",
        UserDetailView.as_view(),
        name="user-detail",
    ),
    path(
        "users/<uuid:user_id>/deletion-preview/",
        UserDeletionPreviewView.as_view(),
        name="user-deletion-preview",
    ),
    path(
        "users/<uuid:user_id>/reset-password/",
        ResetUserPasswordView.as_view(),
        name="reset-user-password",
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
