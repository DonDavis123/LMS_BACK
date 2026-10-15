from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User


def require_platform_admin(current_user: User) -> None:
    if not current_user.is_active:
        raise ValueError("Inactive users cannot manage companies.")
    if current_user.role is not UserRole.PLATFORM_SUPERADMIN:
        raise ValueError("Only platform superadmins can manage companies.")
