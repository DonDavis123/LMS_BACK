from abc import ABC, abstractmethod

from src.modules.lead_capture.domain.entities.lead_form import LeadForm


class LeadFormRepository(ABC):
    """The lead form of ONE company (the implementation is scoped to it)."""

    @abstractmethod
    def create_default(self) -> LeadForm:
        """Create the blocked, unconfigured default form with a fresh token.

        Raises if the company already has one.
        """

    @abstractmethod
    def get(self) -> LeadForm:
        """The company's form. Creates the default one if it is somehow missing."""

    @abstractmethod
    def get_for_update(self) -> LeadForm:
        """Same as ``get`` but locks the row until the transaction ends."""

    @abstractmethod
    def save(self, form: LeadForm) -> LeadForm:
        """Persist the editable settings, the token, the block state and the
        ordered rotation owners. Counters are never written here."""

    @abstractmethod
    def record_submission(
        self, form: LeadForm, assigned_position: int | None
    ) -> None:
        """Count one accepted submission: ``submission_count`` + 1,
        ``last_submission_at`` = now and, when ``assigned_position`` is not
        ``None``, ``last_assigned_position`` = that rotation position.

        Call it inside the transaction that holds ``get_for_update``'s lock.
        """
