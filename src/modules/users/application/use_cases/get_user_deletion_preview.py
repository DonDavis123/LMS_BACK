from uuid import UUID

from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.leads.application.interfaces.lead_repository import (
    LeadRepository,
)
from src.modules.meetings.application.interfaces.meeting_repository import (
    MeetingRepository,
)
from src.modules.notifications.application.interfaces.notification_repository import (
    NotificationRepository,
)
from src.modules.reminders.application.interfaces.reminder_repository import (
    ReminderRepository,
)
from src.modules.tasks.application.interfaces.task_repository import (
    TaskRepository,
)
from src.modules.timeline.application.interfaces.timeline_repository import (
    TimelineRepository,
)
from src.modules.users.application.dto.user_deletion_preview import (
    DeletionImpactDTO,
    DeletionPreviewUserDTO,
    PermanentDeletionsDTO,
    TransferRequiredDTO,
    UserActionDTO,
    UserDeletionPreviewDTO,
)
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User


class GetUserDeletionPreviewUseCase:
    """Read-only summary of what retiring a user would do.

    Counts are the rows DeleteUserUseCase will transfer or delete.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        lead_repository: LeadRepository,
        contact_repository: ContactRepository,
        account_repository: AccountRepository,
        meeting_repository: MeetingRepository,
        task_repository: TaskRepository,
        reminder_repository: ReminderRepository,
        notification_repository: NotificationRepository,
        timeline_repository: TimelineRepository,
    ):
        self.user_repository = user_repository
        self.lead_repository = lead_repository
        self.contact_repository = contact_repository
        self.account_repository = account_repository
        self.meeting_repository = meeting_repository
        self.task_repository = task_repository
        self.reminder_repository = reminder_repository
        self.notification_repository = notification_repository
        self.timeline_repository = timeline_repository

    def execute(
        self,
        current_user: User,
        user_id: UUID,
    ) -> UserDeletionPreviewDTO:
        self._require_superadmin(current_user)

        target_user = self.user_repository.get_by_id(user_id)
        if target_user is None:
            raise ValueError("User not found.")
        if target_user.is_deleted:
            raise ValueError("User has already been deleted.")

        leads = self.lead_repository.count_by_owner_id(user_id)
        contacts = self.contact_repository.count_by_owner_id(user_id)
        accounts = self.account_repository.count_by_owner_id(user_id)
        meetings = self.meeting_repository.count_by_host_id(user_id)
        tasks = self.task_repository.count_by_owner_id(user_id)
        reminders = self.reminder_repository.count_by_user_id(user_id)
        notifications = self.notification_repository.count_by_user_id(user_id)
        timeline = self.timeline_repository.count_by_actor_id(user_id)

        blockers: list[str] = []
        if current_user.id == user_id:
            blockers.append("A superadmin cannot delete their own account.")
        can_retire = not blockers

        # The timeline is kept on retirement, so it is not related data.
        has_related_data = any(
            count > 0
            for count in (
                leads,
                contacts,
                accounts,
                meetings,
                tasks,
                reminders,
                notifications,
            )
        )
        user_is_blocked = not target_user.is_active

        available_actions: list[str] = []
        if can_retire:
            if not user_is_blocked:
                available_actions.append("BLOCK")
            available_actions.append("TRANSFER_AND_DELETE")

        return UserDeletionPreviewDTO(
            user=DeletionPreviewUserDTO(
                id=target_user.id,
                name=target_user.name,
                email=target_user.email,
            ),
            impact=DeletionImpactDTO(
                leads=leads,
                contacts=contacts,
                accounts=accounts,
                tasks=tasks,
                meetings=meetings,
                reminders=reminders,
                notifications=notifications,
                timeline=timeline,
            ),
            transfer_required=TransferRequiredDTO(
                leads=leads > 0,
                contacts=contacts > 0,
                accounts=accounts > 0,
                meetings=meetings > 0,
            ),
            permanent_deletions=PermanentDeletionsDTO(
                tasks=tasks,
                reminders=reminders,
                notifications=notifications,
            ),
            user_action=UserActionDTO(type="SOFT_DELETE"),
            can_retire=can_retire,
            blockers=tuple(blockers),
            has_related_data=has_related_data,
            user_is_blocked=user_is_blocked,
            available_actions=tuple(available_actions),
        )

    @staticmethod
    def _require_superadmin(current_user: User) -> None:
        if not current_user.is_active:
            raise ValueError("Inactive users cannot manage users.")
        if current_user.role is not UserRole.SUPERADMIN:
            raise ValueError("Only superadmins can manage users.")
