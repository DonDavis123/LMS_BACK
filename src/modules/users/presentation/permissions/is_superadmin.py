from rest_framework.permissions import BasePermission

from src.modules.users.domain.entities.role import UserRole


class IsSuperAdmin(BasePermission):
    message = "Only superadmins can manage users."

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role == UserRole.SUPERADMIN.value
        )
