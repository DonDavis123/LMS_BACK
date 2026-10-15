from rest_framework.exceptions import NotAuthenticated, PermissionDenied

from src.modules.companies.infrastructure.persistence.company_suspension import (
    SUSPENDED_MESSAGE,
    is_company_suspended,
)
from src.modules.shared.application.tenant_context import TenantContext
from src.modules.users.domain.entities.role import UserRole


def get_tenant_context(request) -> TenantContext:
    """Build the TenantContext from the authenticated user.

    The company always comes from ``request.user``. Platform superadmins,
    inactive users and users without a company never get a context, so they
    can never reach company-level data.
    """
    user = getattr(request, "user", None)

    if user is None or not user.is_authenticated:
        raise NotAuthenticated()

    if (
        not user.is_active
        or user.role == UserRole.PLATFORM_SUPERADMIN.value
        or getattr(user, "company_id", None) is None
    ):
        raise PermissionDenied("A company account is required.")

    if is_company_suspended(user.company_id):
        raise PermissionDenied(SUSPENDED_MESSAGE)

    return TenantContext(
        company_id=user.company_id,
        user_id=user.id,
        role=user.role,
    )
