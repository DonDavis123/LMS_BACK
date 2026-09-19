import uuid

from django.db import models
from django.db.models import Q

from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.meetings.domain.enums.meeting_related_record_type import (
    MeetingRelatedRecordType,
)

from .django_meeting_model import DjangoMeetingModel


class DjangoMeetingRelatedRecordModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    meeting = models.ForeignKey(
        DjangoMeetingModel,
        on_delete=models.PROTECT,
        related_name="related_records",
    )

    record_type = models.CharField(
        max_length=20,
        choices=[
            (record_type.value, record_type.value)
            for record_type in MeetingRelatedRecordType
        ],
    )

    lead = models.ForeignKey(
        DjangoLeadModel,
        on_delete=models.PROTECT,
        related_name="meeting_related_records",
        blank=True,
        null=True,
    )

    contact = models.ForeignKey(
        DjangoContactModel,
        on_delete=models.PROTECT,
        related_name="meeting_related_records",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "meeting_related_records"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(record_type=MeetingRelatedRecordType.LEAD.value)
                    & Q(lead__isnull=False)
                    & Q(contact__isnull=True)
                )
                | (
                    Q(record_type=MeetingRelatedRecordType.CONTACT.value)
                    & Q(contact__isnull=False)
                    & Q(lead__isnull=True)
                ),
                name="meeting_related_record_type_match",
            ),
            models.UniqueConstraint(
                fields=["meeting", "lead"],
                name="unique_meeting_related_lead",
            ),
            models.UniqueConstraint(
                fields=["meeting", "contact"],
                name="unique_meeting_related_contact",
            ),
        ]
        indexes = [
            models.Index(fields=["meeting", "record_type"]),
            models.Index(fields=["record_type"]),
        ]
