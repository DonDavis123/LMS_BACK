from src.modules.picklists.application.interfaces.picklist_repository import (
    PicklistRepository,
)
from src.modules.picklists.domain.entities.picklist_catalog import (
    SYSTEM_VALUE,
    get_picklist_field,
)


def resolve_option_value(
    repository: PicklistRepository,
    module: str,
    field: str,
    value: str | None,
    current_value: str | None = None,
) -> str:
    """Turn what a client sent into the exact text to store, or raise ValueError.

    - blank / missing  -> the built-in "None" option;
    - an active option -> its canonical text (so "web research" is stored as
      "Web Research");
    - a hidden or unknown value is only accepted when it is the record's
      *current* value, so editing an unrelated field of an old record never
      fails because an admin hid one of its options later.
    """
    definition = get_picklist_field(module, field)

    if value is None or (isinstance(value, str) and not value.strip()):
        return SYSTEM_VALUE

    text = " ".join(str(value).split())
    repository.ensure_defaults(module)
    option = repository.find_by_value(module, field, text)

    if option is not None and option.is_active:
        return option.value

    if current_value is not None and text.casefold() == current_value.casefold():
        return current_value

    if option is not None:
        raise ValueError(
            f'"{option.value}" is no longer available for {definition.label}. '
            "Choose another option."
        )
    raise ValueError(f'"{text}" is not a valid option for {definition.label}.')
