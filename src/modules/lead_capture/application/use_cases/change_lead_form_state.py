from src.modules.lead_capture.application.dto.lead_form_dto import LeadFormDTO
from src.modules.lead_capture.application.interfaces.lead_form_repository import (
    LeadFormRepository,
)
from src.modules.lead_capture.application.use_cases._common import load_form, to_dto
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.users.application.interfaces.user_repository import UserRepository


class _LockedFormChange:
    """Loads the form under a row lock, changes it, saves it.

    The lock makes two concurrent block / unblock / regenerate calls run one
    after the other instead of overwriting each other.
    """

    def __init__(
        self,
        form_repository: LeadFormRepository,
        user_repository: UserRepository,
        transaction_manager: TransactionManager,
    ):
        self.form_repository = form_repository
        self.user_repository = user_repository
        self.transaction_manager = transaction_manager

    def _change(self, form) -> None:
        raise NotImplementedError

    def execute(self) -> LeadFormDTO:
        def run() -> LeadFormDTO:
            form = load_form(self.form_repository, self.user_repository, lock=True)
            self._change(form)
            saved = self.form_repository.save(form)
            saved.eligible_owner_ids = form.eligible_owner_ids
            return to_dto(saved)

        return self.transaction_manager.execute(run)


class BlockLeadFormUseCase(_LockedFormChange):
    def _change(self, form) -> None:
        form.block()


class UnblockLeadFormUseCase(_LockedFormChange):
    """Rejected (ValueError) while the form is not configured."""

    def _change(self, form) -> None:
        form.unblock()


class RegenerateLeadFormLinkUseCase(_LockedFormChange):
    """New token; the old link stops working as soon as this commits."""

    def _change(self, form) -> None:
        form.regenerate_token()
