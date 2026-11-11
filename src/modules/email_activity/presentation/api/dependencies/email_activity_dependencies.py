from src.modules.contacts.infrastructure.persistence.contacts_repository import (
    DjangoContactRepository,
)
from src.modules.email_activity.application.use_cases.log_email_compose import (
    LogEmailComposeUseCase,
)
from src.modules.email_activity.domain.enums.record_type import RecordType
from src.modules.email_activity.infrastructure.record_lookup import (
    RepositoryRecordLookup,
)
from src.modules.email_activity.infrastructure.timeline_compose_log import (
    TimelineComposeLog,
)
from src.modules.leads.infrastructure.persistence.django_lead_repository import (
    DjangoLeadRepository,
)
from src.modules.shared.application.tenant_context import TenantContext
from src.modules.shared.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)
from src.modules.timeline.domain.enums.timeline_entity_type import TimelineEntityType
from src.modules.timeline.domain.enums.timeline_event_type import TimelineEventType
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import (
    DjangoTimelineRepository,
)
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder


def get_log_email_compose_use_case(ctx: TenantContext) -> LogEmailComposeUseCase:
    timeline_repository = DjangoTimelineRepository(company_id=ctx.company_id)
    return LogEmailComposeUseCase(
        lookups={
            RecordType.LEAD: RepositoryRecordLookup(
                DjangoLeadRepository(company_id=ctx.company_id)
            ),
            RecordType.CONTACT: RepositoryRecordLookup(
                DjangoContactRepository(company_id=ctx.company_id)
            ),
        },
        compose_log=TimelineComposeLog(
            timeline_repository,
            DefaultTimelineRecorder(timeline_repository),
            TimelineEventType.EMAIL_COMPOSED.value,
            {
                RecordType.LEAD: TimelineEntityType.LEAD.value,
                RecordType.CONTACT: TimelineEntityType.CONTACT.value,
            },
        ),
        transaction_manager=DjangoTransactionManager(),
    )
