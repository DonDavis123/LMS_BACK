from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4

from src.modules.leads.application.dto.update_lead import UpdateLeadDTO
from src.modules.leads.application.use_cases.update_lead import UpdateLeadUseCase


class ConvertedLeadIsReadOnlyTests(TestCase):
    def _use_case(self, lead):
        lead_repository = Mock()
        lead_repository.get_by_id.return_value = lead
        timeline_recorder = Mock()
        transaction_manager = Mock()
        use_case = UpdateLeadUseCase(
            lead_repository=lead_repository,
            user_repository=Mock(),
            timeline_recorder=timeline_recorder,
            transaction_manager=transaction_manager,
        )
        return use_case, lead_repository, timeline_recorder, transaction_manager

    def test_converted_lead_cannot_be_updated(self):
        lead = SimpleNamespace(id=uuid4(), is_converted=True)
        use_case, repo, timeline, tx = self._use_case(lead)

        with self.assertRaises(ValueError) as raised:
            use_case.execute(UpdateLeadDTO(lead_id=lead.id, name="New name"))

        self.assertIn("converted", str(raised.exception))
        tx.execute.assert_not_called()
        repo.save.assert_not_called()
        timeline.record.assert_not_called()
