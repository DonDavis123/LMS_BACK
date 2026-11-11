from src.modules.accounts.infrastructure.persistence.django_account_repository import (
    DjangoAccountRepository,
)
from src.modules.accounts.presentation.api.dependencies.account_dependencies import (
    get_accounts_use_case,
)
from src.modules.contacts.infrastructure.persistence.contacts_repository import (
    DjangoContactRepository,
)
from src.modules.contacts.presentation.api.dependencies.contact_dependency import (
    get_contacts_use_case,
)
from src.modules.leads.infrastructure.persistence.django_lead_repository import (
    DjangoLeadRepository,
)
from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_leads_use_case,
)
from src.modules.mailing.application.interfaces.recipient_source import (
    RecipientSource,
)
from src.modules.mailing.application.use_cases.resolve_mail_recipients import (
    ResolveMailRecipientsUseCase,
)
from src.modules.mailing.domain.enums.mail_entity import MailEntity
from src.modules.mailing.infrastructure.django_email_validator import (
    is_valid_email,
)
from src.modules.mailing.infrastructure.recipient_sources import (
    AccountRecipientSource,
    ContactRecipientSource,
    LeadRecipientSource,
)
from src.modules.shared.application.tenant_context import TenantContext


# Every source reads through the list use case of its own module and through
# repositories of the caller's company, so tenant scoping, search and filter
# rules are those of the list screens.
def _contact_source(ctx: TenantContext) -> RecipientSource:
    return ContactRecipientSource(
        get_contacts_use_case(ctx),
        DjangoContactRepository(company_id=ctx.company_id),
        DjangoAccountRepository(company_id=ctx.company_id),
    )


def _lead_source(ctx: TenantContext) -> RecipientSource:
    return LeadRecipientSource(
        get_leads_use_case(ctx),
        DjangoLeadRepository(company_id=ctx.company_id),
    )


def _account_source(ctx: TenantContext) -> RecipientSource:
    return AccountRecipientSource(
        get_accounts_use_case(ctx),
        DjangoAccountRepository(company_id=ctx.company_id),
        DjangoContactRepository(company_id=ctx.company_id),
    )


_SOURCES = {
    MailEntity.CONTACTS: _contact_source,
    MailEntity.LEADS: _lead_source,
    MailEntity.ACCOUNTS: _account_source,
}


def get_resolve_mail_recipients_use_case(
    entity: MailEntity,
    ctx: TenantContext,
) -> ResolveMailRecipientsUseCase:
    return ResolveMailRecipientsUseCase(_SOURCES[entity](ctx), is_valid_email)
