from enum import Enum


class UserRole(str, Enum):
    SUPERADMIN = "SUPERADMIN"
    ADMIN = "ADMIN"
    SALES_MANAGER = "SALES_MANAGER"
    SALES_EXECUTIVE = "SALES_EXECUTIVE"
    PLATFORM_SUPERADMIN = "PLATFORM_SUPERADMIN"


# Roles that can currently be assigned through user management.
MANAGEABLE_ROLES = (
    UserRole.SUPERADMIN,
    UserRole.ADMIN,
)