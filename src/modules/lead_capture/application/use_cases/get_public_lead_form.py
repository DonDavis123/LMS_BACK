from src.modules.lead_capture.application.dto.public_lead_form_dto import (
    PublicLeadFormDTO,
)
from src.modules.lead_capture.application.interfaces.lead_form_repository import (
    LeadFormRepository,
)
from src.modules.lead_capture.application.use_cases._common import load_form
from src.modules.users.application.interfaces.user_repository import UserRepository


class GetPublicLeadFormUseCase:
    """What the public page needs: title, company name, open or closed.

    Repositories are pinned to the company resolved from the link token.
    """

    def __init__(
        self,
        form_repository: LeadFormRepository,
        user_repository: UserRepository,
    ):
        self.form_repository = form_repository
        self.user_repository = user_repository

    def execute(self, company_name: str) -> PublicLeadFormDTO:
        form = load_form(self.form_repository, self.user_repository)
        return PublicLeadFormDTO(
            title=form.title,
            company_name=company_name,
            accepting_responses=form.is_active and form.is_configured,
        )
