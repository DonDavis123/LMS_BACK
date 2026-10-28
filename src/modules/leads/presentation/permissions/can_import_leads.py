from rest_framework.permissions import BasePermission

from src.modules.authentication.application.authorization.lead_permissions import (
    LeadPermissions,
)


class CanImportLeads(BasePermission):
    """ADMIN and SUPERADMIN only (the same roles that see all leads)."""

    message = "Only admins and superadmins can import leads."

    def has_permission(self, request, view):
        return LeadPermissions.can_view_all_leads(request.user)
