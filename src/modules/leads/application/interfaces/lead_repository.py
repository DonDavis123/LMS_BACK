from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.leads.domain.entities.lead import Lead
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class LeadRepository(ABC):

    @abstractmethod
    def save(self, lead: Lead) -> Lead:
        pass

    @abstractmethod
    def get_by_id(self, lead_id: UUID) -> Lead | None:
        pass

    @abstractmethod
    def get_all(self) -> list[Lead]:
        pass

    @abstractmethod
    def get_all_with_owner(self, query: ListQuery) -> PaginatedResult[tuple[Lead, str]]:
        pass
    
    @abstractmethod
    def get_by_id_with_owner(
      self,
      lead_id: UUID,
    ) -> tuple[Lead, str] | None:
      pass

    @abstractmethod
    def transfer_ownership(
        self,
        from_user_id: UUID,
        to_user_id: UUID,
    ) -> int:
        """Reassign every Lead owned by ``from_user_id`` to ``to_user_id``."""
        pass

    @abstractmethod
    def count_by_owner_id(self, owner_id: UUID) -> int:
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> Lead | None:
        """The most recently created non-deleted lead with this email
        (case-insensitive) in the repository's company, or ``None``.

        Converted leads are returned too; the caller decides what to do.
        """
        pass

    @abstractmethod
    def get_dedupe_index(self) -> dict:
        """Everything lead import needs to find duplicates, in ONE query.

        ``{"emails": {normalized_email: {id, name, is_converted}},
        "phones": {last_10_digits: {id, name, is_converted}}}``

        Non-deleted leads of the repository's company only. Converted leads
        are included and flagged. Emails match exactly as ``get_by_email``
        does; a phone key is the last 10 digits of ``phone`` or
        ``mobile_number`` (7 or more digits). When several leads share a key,
        the most recently created one is kept.
        """
        pass

    @abstractmethod
    def bulk_create_for_import(self, leads: list[Lead], import_job_id: UUID) -> int:
        """Insert many new leads in one go (the repository's company), each
        marked with ``import_job_id`` so the import can be undone. Returns how
        many were inserted."""
        pass

    @abstractmethod
    def get_many_for_update(self, lead_ids) -> dict[UUID, Lead]:
        """Lock and return the repository company's non-deleted leads with
        these ids, as ``{id: Lead}`` (converted leads are returned too; the
        caller decides). Must be called inside the caller's transaction."""
        pass

    @abstractmethod
    def bulk_update_fields(self, changes: dict[UUID, dict]) -> int:
        """Apply ``{lead_id: {field: new value}}`` to non-deleted, non-converted
        leads of the repository's company in one go. Only the columns an import
        may change are accepted (``owner_id`` included, ``is_deleted`` /
        ``is_converted`` / company never). Returns how many leads changed."""
        pass
