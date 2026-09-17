from unittest import TestCase

from src.modules.timeline.domain.enums.timeline_entity_type import TimelineEntityType
from src.modules.timeline.domain.enums.timeline_event_type import TimelineEventType


class TimelineEnumTests(TestCase):
    def test_supported_entity_types(self):
        self.assertEqual(TimelineEntityType.LEAD.value, "LEAD")
        self.assertEqual(TimelineEntityType.CONTACT.value, "CONTACT")
        self.assertEqual(TimelineEntityType.ACCOUNT.value, "ACCOUNT")

    def test_supported_event_types(self):
        self.assertEqual(TimelineEventType.TASK_COMPLETED.value, "TASK_COMPLETED")
