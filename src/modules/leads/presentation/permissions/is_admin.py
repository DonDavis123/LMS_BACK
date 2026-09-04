from rest_framework.permissions import BasePermission

from src.modules.authentication.application.authorization.lead_permissions import (
    LeadPermissions,
)


class IsAdmin(BasePermission):

    message = "You do not have permission to view leads."

    def has_permission(self, request, view):
        return LeadPermissions.can_view_all_leads(request.user)