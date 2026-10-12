from rest_framework.permissions import BasePermission

from src.modules.users.domain.entities.role import UserRole


class IsCompanyUser(BasePermission):
    """Authenticated, active user that belongs to a company.

    Platform superadmins are excluded: they have no company and must never
    reach company-level data.
    """

    message = "A company account is required."

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role != UserRole.PLATFORM_SUPERADMIN.value
            and getattr(user, "company_id", None) is not None
        )


class IsPlatformSuperAdmin(BasePermission):
    message = "Only platform superadmins can do this."

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role == UserRole.PLATFORM_SUPERADMIN.value
        )
