from src.modules.contacts.application.interfaces.contact_repository import ContactRepository
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.meetings.application.dto.related_group import RelatedGroup
from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType


def validate_related_groups(
    groups: tuple[RelatedGroup, ...],
    lead_repository: LeadRepository,
    contact_repository: ContactRepository,
) -> None:
    """Validate a meeting's Related To selection.

    Any number of leads and contacts may be combined. Every record must exist
    and be active, and no record (or record type) may be listed twice.
    """
    seen_types: set[MeetingRelatedRecordType] = set()
    for group in groups:
        if not group.record_ids:
            raise ValueError("Related record IDs are required when Related To type is supplied.")
        if group.record_type in seen_types:
            raise ValueError("Duplicate Related To records are not allowed.")
        seen_types.add(group.record_type)
        if len(group.record_ids) != len(set(group.record_ids)):
            raise ValueError("Duplicate Related To records are not allowed.")

        if group.record_type == MeetingRelatedRecordType.LEAD:
            for record_id in group.record_ids:
                lead = lead_repository.get_by_id(record_id)
                if lead is None or lead.is_deleted:
                    raise ValueError("Selected lead not found or is deleted.")
        elif group.record_type == MeetingRelatedRecordType.CONTACT:
            for record_id in group.record_ids:
                contact = contact_repository.get_by_id(record_id)
                if contact is None or contact.is_deleted:
                    raise ValueError("Selected contact not found or is deleted.")
        else:
            raise ValueError("Unsupported Related To type.")
