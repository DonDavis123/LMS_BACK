from src.modules.accounts.presentation.api.dependencies.account_dependencies import (
    get_accounts_use_case,
)
from src.modules.calls.presentation.api.dependencies.call_dependencies import (
    get_calls_use_case,
)
from src.modules.contacts.presentation.api.dependencies.contact_dependency import (
    get_contacts_use_case,
)
from src.modules.exports.application.services.export_definitions import (
    DEFINITIONS,
    ExportDefinition,
)
from src.modules.exports.application.use_cases.export_records import (
    ExportRecordsUseCase,
)
from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_leads_use_case,
)
from src.modules.meetings.presentation.api.dependencies.meeting_dependencies import (
    get_meetings_use_case,
)
from src.modules.shared.application.tenant_context import TenantContext
from src.modules.tasks.presentation.api.dependencies.task_dependencies import (
    get_tasks_use_case,
)

# Each export reads through the list use case of its own module, which is
# already scoped to the caller's company.
_LIST_USE_CASES = {
    "leads": get_leads_use_case,
    "accounts": get_accounts_use_case,
    "contacts": get_contacts_use_case,
    "tasks": get_tasks_use_case,
    "calls": get_calls_use_case,
    "meetings": get_meetings_use_case,
}


def get_export_definition(entity: str) -> ExportDefinition | None:
    return DEFINITIONS.get(entity)


def get_export_records_use_case(
    entity: str,
    ctx: TenantContext,
) -> ExportRecordsUseCase:
    return ExportRecordsUseCase(
        _LIST_USE_CASES[entity](ctx),
        DEFINITIONS[entity],
    )
