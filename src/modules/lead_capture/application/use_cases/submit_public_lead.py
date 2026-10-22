from collections.abc import Callable

from src.modules.lead_capture.application.dto.public_lead_form_dto import (
    PublicLeadSubmissionDTO,
)
from src.modules.lead_capture.application.interfaces.lead_form_repository import (
    LeadFormRepository,
)
from src.modules.lead_capture.application.use_cases._common import load_form
from src.modules.lead_capture.domain.entities.assignment_mode import AssignmentMode
from src.modules.leads.application.dto.create_lead_dto import CreateLeadDTO
from src.modules.leads.application.use_cases.create_lead import CreateLeadUseCase
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.shared.application.tenant_context import TenantContext
from src.modules.users.application.interfaces.user_repository import UserRepository

NOT_ACCEPTING_MESSAGE = "This form is no longer accepting responses"


class FormNotAcceptingResponses(Exception):
    """Blocked, not configured, no eligible owner or lead source invalid.

    One error for all of them on purpose: the visitor is never told why.
    """


class SubmitPublicLeadUseCase:
    def __init__(
        self,
        form_repository: LeadFormRepository,
        user_repository: UserRepository,
        create_lead_factory: Callable[[TenantContext], CreateLeadUseCase],
        transaction_manager: TransactionManager,
    ):
        self.form_repository = form_repository
        self.user_repository = user_repository
        self.create_lead_factory = create_lead_factory
        self.transaction_manager = transaction_manager

    def execute(self, submission: PublicLeadSubmissionDTO) -> None:
        def run() -> None:
            # Lock the form for EVERY submission: it serialises the rotation
            # pointer and the counters, and a block that commits first wins.
            form = load_form(self.form_repository, self.user_repository, lock=True)
            if not form.is_active or not form.is_configured:
                raise FormNotAcceptingResponses()

            owner = form.pick_owner()
            if owner is None:
                raise FormNotAcceptingResponses()
            owner_user = self.user_repository.get_by_id(owner.id)
            if owner_user is None:
                raise FormNotAcceptingResponses()

            # company_id comes from the company-pinned form, never from the
            # request. The chosen owner "creates" the lead.
            role = getattr(owner_user.role, "value", owner_user.role)
            ctx = TenantContext(
                company_id=form.company_id, user_id=owner.id, role=str(role)
            )

            dto = CreateLeadDTO(
                name=submission.name,
                title=None,
                company_name=None,
                email=submission.email,
                mobile_number=None,
                phone=submission.phone,
                lead_source=form.lead_source,
                lead_status=None,
                industry=None,
                rating=None,
                website=None,
                number_of_employees=None,
                annual_revenue=None,
                owner_id=owner.id,
                address=None,
                city=None,
                state=None,
                country=None,
                postal_code=None,
                description=submission.description,
            )
            try:
                self.create_lead_factory(ctx).execute(dto, owner.id)
            except ValueError:
                # e.g. the lead source is no longer a valid option. Roll
                # back and answer like any other "closed" form.
                raise FormNotAcceptingResponses()

            self.form_repository.record_submission(
                form,
                assigned_position=(
                    owner.position
                    if form.assignment_mode is AssignmentMode.ROTATION
                    else None
                ),
            )

        self.transaction_manager.execute(run)
