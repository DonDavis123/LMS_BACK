from src.modules.users.domain.entities.role import UserRole


class LeadPermissions:

    @staticmethod
    def can_view_all_leads(user) -> bool:
        return (
            user.is_authenticated
            and user.role in {
                UserRole.SUPERADMIN,
                UserRole.ADMIN,
            }
        )