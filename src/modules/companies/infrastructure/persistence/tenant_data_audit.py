from dataclasses import dataclass

from django.db.models import F, Model

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.meetings.infrastructure.persistence.models import (
    DjangoMeetingModel,
    DjangoMeetingParticipantModel,
    DjangoMeetingRelatedRecordModel,
)
from src.modules.notifications.infrastructure.persistence.models import (
    DjangoNotificationModel,
)
from src.modules.reminders.infrastructure.persistence.models import (
    DjangoReminderModel,
)
from src.modules.tasks.infrastructure.persistence.models import DjangoTaskModel
from src.modules.timeline.infrastructure.persistence.models import TimelineEvent
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.infrastructure.persistence.models import User
from src.modules.users.infrastructure.persistence.user_audit_log_model import (
    DjangoUserAuditLogModel,
)

PLATFORM_ROLE = UserRole.PLATFORM_SUPERADMIN.value

SECTION_NULL = "NULL company_id"
SECTION_MISMATCH = "Cross-company mismatch"
SECTION_USERS = "User / company consistency"


@dataclass(frozen=True)
class AuditCheck:
    section: str
    name: str
    count: int


# (label, model) - rows whose company_id is NULL. Users are handled separately
# because platform superadmins are expected to have no company.
NULL_COMPANY_CHECKS: tuple[tuple[str, type[Model]], ...] = (
    ("leads", DjangoLeadModel),
    ("accounts", DjangoAccountModel),
    ("contacts", DjangoContactModel),
    ("tasks", DjangoTaskModel),
    ("meetings", DjangoMeetingModel),
    ("reminders", DjangoReminderModel),
    ("notifications", DjangoNotificationModel),
    ("timeline events", TimelineEvent),
)

# (label, model, company path on the row, company path on the related row).
# A row is a mismatch when both companies are set and they differ; NULLs are
# reported by the NULL checks instead.
MISMATCH_CHECKS: tuple[tuple[str, type[Model], str, str], ...] = (
    ("lead vs owner", DjangoLeadModel, "company", "owner__company"),
    ("account vs account_owner", DjangoAccountModel, "company", "account_owner__company"),
    ("contact vs account", DjangoContactModel, "company", "account__company"),
    ("contact vs contact_owner", DjangoContactModel, "company", "contact_owner__company"),
    ("task vs owner", DjangoTaskModel, "company", "owner__company"),
    ("task vs assigned_to", DjangoTaskModel, "company", "assigned_to__company"),
    ("task vs lead", DjangoTaskModel, "company", "lead__company"),
    ("task vs contact", DjangoTaskModel, "company", "contact__company"),
    ("task vs account", DjangoTaskModel, "company", "account__company"),
    ("meeting vs host", DjangoMeetingModel, "company", "host__company"),
    (
        "meeting participant (user) vs meeting",
        DjangoMeetingParticipantModel,
        "meeting__company",
        "user__company",
    ),
    (
        "meeting participant (lead) vs meeting",
        DjangoMeetingParticipantModel,
        "meeting__company",
        "lead__company",
    ),
    (
        "meeting participant (contact) vs meeting",
        DjangoMeetingParticipantModel,
        "meeting__company",
        "contact__company",
    ),
    (
        "meeting related lead vs meeting",
        DjangoMeetingRelatedRecordModel,
        "meeting__company",
        "lead__company",
    ),
    (
        "meeting related contact vs meeting",
        DjangoMeetingRelatedRecordModel,
        "meeting__company",
        "contact__company",
    ),
    ("reminder vs user", DjangoReminderModel, "company", "user__company"),
    ("reminder vs task", DjangoReminderModel, "company", "task__company"),
    ("reminder vs meeting", DjangoReminderModel, "company", "meeting__company"),
    ("notification vs user", DjangoNotificationModel, "company", "user__company"),
    ("notification vs task", DjangoNotificationModel, "company", "task__company"),
    ("notification vs meeting", DjangoNotificationModel, "company", "meeting__company"),
    ("notification vs reminder", DjangoNotificationModel, "company", "reminder__company"),
    ("timeline event vs actor", TimelineEvent, "company", "actor__company"),
)


def _mismatch_count(model: type[Model], left: str, right: str) -> int:
    # One COUNT with joins; the database compares the two company columns.
    return (
        model._default_manager.filter(
            **{f"{left}__isnull": False, f"{right}__isnull": False},
        )
        .exclude(**{left: F(right)})
        .count()
    )


def run_tenant_data_audit() -> list[AuditCheck]:
    checks: list[AuditCheck] = []

    # 1. NULL company_id counts
    checks.append(
        AuditCheck(
            SECTION_NULL,
            "non-platform users",
            User.objects.filter(company__isnull=True)
            .exclude(role=PLATFORM_ROLE)
            .count(),
        )
    )
    for label, model in NULL_COMPANY_CHECKS:
        checks.append(
            AuditCheck(
                SECTION_NULL,
                label,
                model._default_manager.filter(company__isnull=True).count(),
            )
        )
    checks.append(
        AuditCheck(
            SECTION_NULL,
            "user audit logs",
            DjangoUserAuditLogModel.objects.filter(
                company_id__isnull=True,
            ).count(),
        )
    )

    # 2. Cross-company mismatches
    for label, model, left, right in MISMATCH_CHECKS:
        checks.append(
            AuditCheck(
                SECTION_MISMATCH,
                label,
                _mismatch_count(model, left, right),
            )
        )

    # 3. User / company consistency
    checks.append(
        AuditCheck(
            SECTION_USERS,
            "platform superadmins with a company",
            User.objects.filter(
                role=PLATFORM_ROLE,
                company__isnull=False,
            ).count(),
        )
    )
    checks.append(
        AuditCheck(
            SECTION_USERS,
            "non-platform users without a company",
            User.objects.filter(company__isnull=True)
            .exclude(role=PLATFORM_ROLE)
            .count(),
        )
    )

    return checks
