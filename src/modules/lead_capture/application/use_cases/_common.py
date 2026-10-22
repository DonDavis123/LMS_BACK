from src.modules.lead_capture.application.dto.lead_form_dto import (
    FormOwnerDTO,
    LeadFormDTO,
)
from src.modules.lead_capture.application.interfaces.lead_form_repository import (
    LeadFormRepository,
)
from src.modules.lead_capture.domain.entities.lead_form import FormOwner, LeadForm
from src.modules.users.application.interfaces.user_repository import UserRepository


def load_form(
    form_repository: LeadFormRepository,
    user_repository: UserRepository,
    *,
    lock: bool = False,
) -> LeadForm:
    """The company's form plus who may own leads *right now*.

    Eligibility is the same rule the leads module uses for lead owners
    (``UserRepository.get_lead_owners``: active, not deleted, same company,
    ADMIN or SUPERADMIN) and is looked up on every call, never stored.
    """
    form = form_repository.get_for_update() if lock else form_repository.get()
    form.eligible_owner_ids = frozenset(
        user.id for user in user_repository.get_lead_owners()
    )
    return form


def _owner_dto(owner: FormOwner | None) -> FormOwnerDTO | None:
    if owner is None:
        return None
    return FormOwnerDTO(id=owner.id, name=owner.name, position=owner.position)


def to_dto(form: LeadForm) -> LeadFormDTO:
    return LeadFormDTO(
        id=form.id,
        title=form.title,
        lead_source=form.lead_source or None,
        assignment_mode=form.assignment_mode.value,
        single_owner=_owner_dto(form.single_owner),
        rotation_owners=[_owner_dto(owner) for owner in form.rotation_owners],
        is_active=form.is_active,
        is_configured=form.is_configured,
        needs_attention=form.needs_attention,
        public_token=form.public_token,
        submission_count=form.submission_count,
        last_submission_at=form.last_submission_at,
        created_at=form.created_at,
        updated_at=form.updated_at,
    )
