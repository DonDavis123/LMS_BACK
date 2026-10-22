from uuid import UUID

from src.modules.lead_capture.application.dto.lead_form_dto import (
    _UNSET,
    LeadFormDTO,
    UpdateLeadFormDTO,
)
from src.modules.lead_capture.application.interfaces.lead_form_repository import (
    LeadFormRepository,
)
from src.modules.lead_capture.application.use_cases._common import load_form, to_dto
from src.modules.lead_capture.domain.entities.assignment_mode import AssignmentMode
from src.modules.lead_capture.domain.entities.lead_form import (
    MAX_ROTATION_OWNERS,
    TITLE_MAX_LENGTH,
    FormOwner,
    LeadForm,
)
from src.modules.picklists.application.interfaces.picklist_repository import (
    PicklistRepository,
)
from src.modules.picklists.application.services.option_validation import (
    resolve_option_value,
)
from src.modules.picklists.domain.entities.picklist_catalog import SYSTEM_VALUE
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.users.application.interfaces.user_repository import UserRepository

OWNER_NOT_ELIGIBLE = "Selected owner must be an active ADMIN or SUPERADMIN of this company."


class UpdateLeadFormUseCase:
    def __init__(
        self,
        form_repository: LeadFormRepository,
        user_repository: UserRepository,
        picklist_repository: PicklistRepository,
        transaction_manager: TransactionManager,
    ):
        self.form_repository = form_repository
        self.user_repository = user_repository
        self.picklist_repository = picklist_repository
        self.transaction_manager = transaction_manager

    def execute(self, data: UpdateLeadFormDTO) -> LeadFormDTO:
        def run() -> LeadFormDTO:
            form = load_form(self.form_repository, self.user_repository, lock=True)
            was_configured = form.is_configured

            # Same user list the leads module offers as lead owners.
            owners = {u.id: u for u in self.user_repository.get_lead_owners()}

            self._apply(form, data, owners)

            if form.is_active and was_configured and not form.is_configured:
                raise ValueError(
                    "This change would leave the live form without a lead source "
                    "or an eligible owner. Block the form first."
                )

            saved = self.form_repository.save(form)
            saved.eligible_owner_ids = form.eligible_owner_ids
            return to_dto(saved)

        return self.transaction_manager.execute(run)

    # ------------------------------------------------------------------

    def _apply(self, form: LeadForm, data: UpdateLeadFormDTO, owners: dict) -> None:
        if data.title is not _UNSET:
            form.title = self._title(data.title)

        if data.lead_source is not _UNSET:
            form.lead_source = self._lead_source(data.lead_source, form.lead_source)

        owner_fields_sent = False

        if data.assignment_mode is not _UNSET:
            owner_fields_sent = True
            try:
                form.assignment_mode = AssignmentMode(data.assignment_mode)
            except ValueError:
                raise ValueError(
                    "assignment_mode must be SINGLE_OWNER or ROTATION."
                ) from None

        if data.single_owner_id is not _UNSET:
            owner_fields_sent = True
            form.single_owner = self._single_owner(data.single_owner_id, owners)

        if data.rotation_owner_ids is not _UNSET:
            owner_fields_sent = True
            rotation = self._rotation_owners(data.rotation_owner_ids, owners)
            if [o.id for o in rotation] != [o.id for o in form.rotation_owners]:
                # The order changed, so the "who is next" pointer is stale.
                form.last_assigned_position = None
            form.rotation_owners = rotation

        # A draft can be saved piece by piece (e.g. only the title), but as
        # soon as the owner setup is touched it has to be complete for the
        # chosen mode.
        if owner_fields_sent and not form.has_eligible_owner:
            if form.assignment_mode is AssignmentMode.SINGLE_OWNER:
                raise ValueError(
                    "single_owner_id is required when assignment_mode is SINGLE_OWNER."
                )
            raise ValueError(
                "rotation_owner_ids needs at least one owner when "
                "assignment_mode is ROTATION."
            )

    @staticmethod
    def _title(raw) -> str:
        if not isinstance(raw, str):
            raise ValueError("Title must be text.")
        title = " ".join(raw.split())
        if not title:
            raise ValueError("Title cannot be empty.")
        if len(title) > TITLE_MAX_LENGTH:
            raise ValueError(f"Title cannot be longer than {TITLE_MAX_LENGTH} characters.")
        if any(ord(char) < 32 for char in title):
            raise ValueError("Title contains invalid characters.")
        return title

    def _lead_source(self, raw, current: str) -> str:
        """Same validation as a Lead's source: one of the company's active
        Lead Source options. Blank / null / the built-in "None" mean "not
        chosen yet" (the form is then simply not configured)."""
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return ""
        if not isinstance(raw, str):
            raise ValueError("lead_source must be text.")

        resolved = resolve_option_value(
            self.picklist_repository,
            "leads",
            "lead_source",
            raw,
            current_value=current or None,
        )
        return "" if resolved == SYSTEM_VALUE else resolved

    @staticmethod
    def _single_owner(owner_id: UUID | None, owners: dict) -> FormOwner | None:
        if owner_id is None:
            return None
        user = owners.get(owner_id)
        if user is None:
            # Unknown, other company, inactive, deleted or wrong role all
            # look the same, so nothing leaks about other companies.
            raise ValueError(OWNER_NOT_ELIGIBLE)
        return FormOwner(id=user.id, name=user.name)

    @staticmethod
    def _rotation_owners(owner_ids: list[UUID], owners: dict) -> list[FormOwner]:
        if not owner_ids:
            raise ValueError("rotation_owner_ids needs at least one owner.")
        if len(owner_ids) > MAX_ROTATION_OWNERS:
            raise ValueError(
                f"A rotation cannot have more than {MAX_ROTATION_OWNERS} owners."
            )
        if len(set(owner_ids)) != len(owner_ids):
            raise ValueError("rotation_owner_ids cannot contain the same user twice.")

        result = []
        for position, owner_id in enumerate(owner_ids):
            user = owners.get(owner_id)
            if user is None:
                raise ValueError(OWNER_NOT_ELIGIBLE)
            result.append(FormOwner(id=user.id, name=user.name, position=position))
        return result
