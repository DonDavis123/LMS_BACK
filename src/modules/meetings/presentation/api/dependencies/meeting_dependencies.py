from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.leads.infrastructure.persistence.django_lead_repository import DjangoLeadRepository
from src.modules.meetings.application.use_cases.create_meeting import CreateMeetingUseCase
from src.modules.meetings.application.use_cases.delete_meeting import DeleteMeetingUseCase
from src.modules.meetings.application.use_cases.get_meeting import GetMeetingUseCase
from src.modules.meetings.application.use_cases.get_meetings import GetMeetingsUseCase
from src.modules.meetings.application.use_cases.update_meeting import UpdateMeetingUseCase
from src.modules.meetings.infrastructure.persistence.django_meeting_repository import DjangoMeetingRepository
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository


def recorder():
    return DefaultTimelineRecorder(DjangoTimelineRepository())


def transaction_manager():
    return DjangoTransactionManager()


def get_create_meeting_use_case() -> CreateMeetingUseCase:
    return CreateMeetingUseCase(
        DjangoMeetingRepository(),
        DjangoUserRepository(),
        DjangoLeadRepository(),
        DjangoContactRepository(),
        recorder(),
        transaction_manager(),
    )


def get_meetings_use_case() -> GetMeetingsUseCase:
    return GetMeetingsUseCase(DjangoMeetingRepository())


def get_meeting_use_case() -> GetMeetingUseCase:
    return GetMeetingUseCase(DjangoMeetingRepository())


def get_update_meeting_use_case() -> UpdateMeetingUseCase:
    return UpdateMeetingUseCase(
        DjangoMeetingRepository(),
        DjangoUserRepository(),
        DjangoLeadRepository(),
        DjangoContactRepository(),
        recorder(),
        transaction_manager(),
    )


def get_delete_meeting_use_case() -> DeleteMeetingUseCase:
    return DeleteMeetingUseCase(
        DjangoMeetingRepository(),
        recorder(),
        transaction_manager(),
    )
