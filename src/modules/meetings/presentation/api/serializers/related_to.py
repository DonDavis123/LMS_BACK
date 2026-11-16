from rest_framework import serializers

from src.modules.meetings.application.dto.related_group import RelatedGroup
from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType


class RelatedToGroupSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=[(item.value, item.value) for item in MeetingRelatedRecordType]
    )
    ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
    )


class RelatedToSerializerMixin:
    """Lets ``related_to`` be a list of ``{type, ids}`` groups.

    A meeting can be related to any number of leads and contacts, e.g.
    ``[{"type": "LEAD", "ids": [...]}, {"type": "CONTACT", "ids": [...]}]``.
    The earlier single-object form ``{"type": "LEAD", "ids": [...]}`` is still
    accepted and treated as a one-group list.
    """

    def to_internal_value(self, data):
        related_to = data.get("related_to") if hasattr(data, "get") else None
        if isinstance(related_to, dict):
            data = data.copy() if hasattr(data, "copy") else dict(data)
            data["related_to"] = [related_to]
        return super().to_internal_value(data)


def related_groups_from_validated(related_to) -> tuple[RelatedGroup, ...]:
    """Build RelatedGroups from validated ``related_to`` (``None`` means none).

    Groups without ids are dropped; groups of the same type are merged so the
    use case can reject a record that is listed twice.
    """
    merged: dict[MeetingRelatedRecordType, list] = {}
    for group in related_to or []:
        ids = tuple(group["ids"])
        if not ids:
            continue
        merged.setdefault(MeetingRelatedRecordType(group["type"]), []).extend(ids)
    return tuple(
        RelatedGroup(record_type=record_type, record_ids=tuple(ids))
        for record_type, ids in merged.items()
    )
