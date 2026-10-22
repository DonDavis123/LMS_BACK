from src.modules.lead_capture.application.dto.lead_form_dto import LeadFormDTO
from src.modules.lead_capture.application.interfaces.lead_form_repository import (
    LeadFormRepository,
)
from src.modules.lead_capture.application.use_cases._common import load_form, to_dto
from src.modules.users.application.interfaces.user_repository import UserRepository


class GetLeadFormUseCase:
    def __init__(
        self,
        form_repository: LeadFormRepository,
        user_repository: UserRepository,
    ):
        self.form_repository = form_repository
        self.user_repository = user_repository

    def execute(self) -> LeadFormDTO:
        return to_dto(load_form(self.form_repository, self.user_repository))
