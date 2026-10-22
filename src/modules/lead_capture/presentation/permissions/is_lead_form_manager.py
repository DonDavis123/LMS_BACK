from src.modules.users.presentation.permissions.is_superadmin import IsSuperAdmin


class IsLeadFormManager(IsSuperAdmin):
    """Company SUPERADMIN only (reuses the users module's role check)."""

    message = "Only company superadmins can manage the lead capture form."
