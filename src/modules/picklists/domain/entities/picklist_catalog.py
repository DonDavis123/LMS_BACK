from dataclasses import dataclass

from src.modules.leads.domain.entities.lead_industry import LeadIndustry
from src.modules.leads.domain.entities.lead_rating import LeadRating
from src.modules.leads.domain.entities.lead_source import LeadSource
from src.modules.leads.domain.entities.lead_status import LeadStatus

# The option every field starts with. It is what a record gets when nothing
# is chosen, so it is a protected "system" option that can never be renamed,
# hidden or deleted.
SYSTEM_VALUE = "None"

# Safety net so a runaway client cannot create thousands of options.
MAX_OPTIONS_PER_FIELD = 200


@dataclass(frozen=True)
class PicklistField:
    """One customisable dropdown, e.g. Leads -> Lead Source."""

    module: str
    key: str
    label: str
    max_length: int
    default_values: tuple[str, ...]


def _values(enum_class) -> tuple[str, ...]:
    return tuple(member.value for member in enum_class)


# The code-defined enums are now only the *starting point* (seed data) for a
# company's options. After seeding, each company edits its own copy.
_FIELDS = (
    PicklistField("leads", "lead_source", "Lead Source", 100, _values(LeadSource)),
    PicklistField("leads", "lead_status", "Lead Status", 100, _values(LeadStatus)),
    PicklistField("leads", "industry", "Industry", 150, _values(LeadIndustry)),
    PicklistField("leads", "rating", "Rating", 100, _values(LeadRating)),
)

_BY_KEY = {(field.module, field.key): field for field in _FIELDS}


def get_picklist_field(module: str, field: str) -> PicklistField:
    definition = _BY_KEY.get((module, field))
    if definition is None:
        raise ValueError("Unknown picklist field.")
    return definition


def get_module_fields(module: str) -> list[PicklistField]:
    fields = [item for item in _FIELDS if item.module == module]
    if not fields:
        raise ValueError("Unknown picklist module.")
    return fields
