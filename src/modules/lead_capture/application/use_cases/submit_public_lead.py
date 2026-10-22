from collections.abc import Callable

from django.conf import settings
from django.utils import timezone

from src.modules.lead_capture.application.dto.public_lead_form_dto import (
    PublicLeadSubmissionDTO,
)
from src.modules.lead_capture.application.interfaces.lead_form_repository import (
    LeadFormRepository,
)
from src.modules.lead_capture.application.use_cases._common import load_form
from src.modules.lead_capture.domain.entities.assignment_mode import AssignmentMode
from src.modules.leads.application.dto.create_lead_dto import CreateLeadDTO
from src.modules.leads.application.dto.update_lead import UpdateLeadDTO
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.leads.application.use_cases.create_lead import CreateLeadUseCase
from src.modules.leads.application.use_cases.update_lead import UpdateLeadUseCase
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
        lead_repository: LeadRepository,
        create_lead_factory: Callable[[TenantContext], CreateLeadUseCase],
        update_lead_factory: Callable[[TenantContext], UpdateLeadUseCase],
        transaction_manager: TransactionManager,
    ):
        self.form_repository = form_repository
        self.user_repository = user_repository
        self.lead_repository = lead_repository
        self.create_lead_factory = create_lead_factory
        self.update_lead_factory = update_lead_factory
        self.transaction_manager = transaction_manager

    def execute(self, submission: PublicLeadSubmissionDTO) -> None:
        def run() -> None:
            # Lock the form for EVERY submission: it serialises the rotation
            # pointer and the counters, and a block that commits first wins.
            form = load_form(self.form_repository, self.user_repository, lock=True)
            if not form.is_active or not form.is_configured:
                raise FormNotAcceptingResponses()

            # Daily cap: checked under the form lock and before anything is
            # created, so concurrent submissions cannot overshoot it. Answered
            # like any other closed form (410).
            if form.has_reached_daily_cap(
                timezone.localdate(), settings.LEAD_CAPTURE_DAILY_CAP
            ):
                raise FormNotAcceptingResponses()

            # Same email already in this company (case-insensitive, not
            # deleted): update that lead instead of creating a second one.
            # A converted lead is a closed record, so it is ignored and the
            # submission becomes a new lead below.
            existing = self.lead_repository.get_by_email(submission.email)
            if existing is not None and not existing.is_converted:
                self._update_existing(form, existing, submission)
                # No owner was picked: the rotation pointer must not move.
                self.form_repository.record_submission(form, assigned_position=None)
                return

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

    def _update_existing(self, form, existing, submission) -> None:
        actor = self._acting_user(form, existing)

        separator = f"--- {timezone.localdate():%d %b %Y} ---"
        old_description = existing.description or ""
        if old_description.strip():
            description = f"{old_description}\n\n{separator}\n{submission.description}"
        else:
            description = f"{separator}\n{submission.description}"

        role = getattr(actor.role, "value", actor.role)
        ctx = TenantContext(
            company_id=form.company_id, user_id=actor.id, role=str(role)
        )
        # Only these three fields are set; everything else stays as it is
        # (owner, source, status, ... are left at the "unset" default).
        dto = UpdateLeadDTO(
            lead_id=existing.id,
            name=submission.name,
            phone=submission.phone,
            description=description,
        )
        try:
            self.update_lead_factory(ctx).execute(dto, actor.id)
        except ValueError:
            # Roll back and answer like any other "closed" form.
            raise FormNotAcceptingResponses()

    def _acting_user(self, form, existing):
        """The lead's current owner; if that user cannot be loaded, the
        form's single owner or first eligible rotation owner. Never touches
        the rotation pointer (``pick_owner`` is not used on purpose)."""
        user = self.user_repository.get_by_id(existing.owner_id)
        if user is not None:
            return user

        if form.assignment_mode is AssignmentMode.ROTATION:
            fallback = next(iter(form.eligible_rotation_owners), None)
        else:
            fallback = form.single_owner if form.has_eligible_owner else None
        user = (
            self.user_repository.get_by_id(fallback.id) if fallback is not None else None
        )
        if user is None:
            raise FormNotAcceptingResponses()
        return user
