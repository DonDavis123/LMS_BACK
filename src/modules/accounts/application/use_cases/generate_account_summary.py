from uuid import UUID

from src.modules.accounts.application.dto.account_summary import AccountSummaryResponseDTO
from src.modules.accounts.application.interfaces.account_repository import AccountRepository
from src.modules.accounts.application.interfaces.account_summary_generator import (
    AccountSummaryGenerator,
    AccountSummaryUnavailableError,
)
from src.modules.accounts.application.interfaces.account_summary_repository import (
    AccountSummaryRepository,
)
from src.modules.accounts.application.services.account_summary_dossier import (
    MAX_CALLS,
    MAX_CONTACTS,
    MAX_TIMELINE_EVENTS,
    build_account_dossier,
)
from src.modules.accounts.domain.entities.account_summary import AccountSummary
from src.modules.calls.application.interfaces.call_recording_transcript_repository import (
    CallRecordingTranscriptRepository,
)
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.contacts.application.interfaces.contact_repository import ContactRepository
from src.modules.timeline.application.interfaces.timeline_repository import TimelineRepository


class GenerateAccountSummaryUseCase:
    """Writes a short "where does this account stand" summary from its history.

    Runs only when a user asks for it. It reads the account, its contacts, its
    timeline (which also carries the deals, tasks and calls of its contacts)
    and the calls logged with it (with the summaries of transcribed
    recordings), all scoped to the caller's company by the repositories.

    The result is stored as the account's current summary. A refresh deletes
    the previous summary permanently and stores the new one in its place; when
    the model fails nothing is touched and the previous summary stays.
    """

    def __init__(
        self,
        account_repository: AccountRepository,
        contact_repository: ContactRepository,
        timeline_repository: TimelineRepository,
        call_repository: CallRepository,
        transcript_repository: CallRecordingTranscriptRepository,
        summary_generator: AccountSummaryGenerator,
        summary_repository: AccountSummaryRepository | None = None,
    ):
        self.account_repository = account_repository
        self.contact_repository = contact_repository
        self.timeline_repository = timeline_repository
        self.call_repository = call_repository
        self.transcript_repository = transcript_repository
        self.summary_generator = summary_generator
        # ``None`` keeps the old behaviour: generate without storing.
        self.summary_repository = summary_repository

    def execute(self, account_id: UUID) -> AccountSummaryResponseDTO:
        # Check the setup first: no point reading the history without a model.
        if not self.summary_generator.is_configured():
            raise AccountSummaryUnavailableError("Account summaries are not configured.")

        found = self.account_repository.get_by_id_with_owner(account_id)
        if found is None:
            raise ValueError("Account not found.")
        account, owner_name = found

        contacts = self.contact_repository.get_by_account_id_with_owner(account.id)[:MAX_CONTACTS]
        events = self.timeline_repository.get_for_entity("ACCOUNT", account.id)[:MAX_TIMELINE_EVENTS]
        calls = self.call_repository.get_by_account_id(account.id, limit=MAX_CALLS)
        call_summaries = self._call_summaries([item.call.id for item in calls])

        dossier = build_account_dossier(
            account=account,
            owner_name=owner_name,
            contacts=contacts,
            events=events,
            calls=calls,
            call_summaries=call_summaries,
        )

        # Raises AccountSummaryError on failure, before anything is deleted.
        result = self.summary_generator.generate(dossier)

        summary = AccountSummary.create(
            account_id=account.id,
            headline=result.headline,
            key_points=result.key_points,
            next_steps=result.next_steps,
            model_name=result.model_name,
            timeline_events_used=len(events),
            calls_used=len(calls),
            contacts_used=len(contacts),
        )

        if self.summary_repository is not None:
            # Old summary deleted + new one stored, in one transaction.
            summary = self.summary_repository.replace_for_account(summary)

        return AccountSummaryResponseDTO.from_entity(summary)

    def _call_summaries(self, call_ids: list[UUID]) -> dict:
        grouped: dict = {}
        if not call_ids:
            return grouped
        for transcript in self.transcript_repository.get_completed_for_calls(call_ids):
            grouped.setdefault(transcript.call_id, []).append(transcript)
        return grouped
