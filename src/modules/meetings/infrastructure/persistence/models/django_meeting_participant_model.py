import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.meetings.domain.enums.meeting_participant_type import (
    MeetingParticipantType,
)

from .django_meeting_model import DjangoMeetingModel


class DjangoMeetingParticipantModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    meeting = models.ForeignKey(
        DjangoMeetingModel,
        on_delete=models.PROTECT,
        related_name="participants",
    )

    participant_type = models.CharField(
        max_length=20,
        choices=[
            (participant_type.value, participant_type.value)
            for participant_type in MeetingParticipantType
        ],
    )

    lead = models.ForeignKey(
        DjangoLeadModel,
        on_delete=models.PROTECT,
        related_name="meeting_participants",
        blank=True,
        null=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="meeting_participants",
        blank=True,
        null=True,
    )

    contact = models.ForeignKey(
        DjangoContactModel,
        on_delete=models.PROTECT,
        related_name="meeting_participants",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "meeting_participants"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(participant_type=MeetingParticipantType.LEAD.value)
                    & Q(lead__isnull=False)
                    & Q(user__isnull=True)
                    & Q(contact__isnull=True)
                )
                | (
                    Q(participant_type=MeetingParticipantType.USER.value)
                    & Q(user__isnull=False)
                    & Q(lead__isnull=True)
                    & Q(contact__isnull=True)
                )
                | (
                    Q(participant_type=MeetingParticipantType.CONTACT.value)
                    & Q(contact__isnull=False)
                    & Q(lead__isnull=True)
                    & Q(user__isnull=True)
                ),
                name="meeting_participant_type_match",
            ),
            models.UniqueConstraint(
                fields=["meeting", "lead"],
                name="unique_meeting_participant_lead",
            ),
            models.UniqueConstraint(
                fields=["meeting", "user"],
                name="unique_meeting_participant_user",
            ),
            models.UniqueConstraint(
                fields=["meeting", "contact"],
                name="unique_meeting_participant_contact",
            ),
        ]
        indexes = [
            models.Index(fields=["meeting", "participant_type"]),
            models.Index(fields=["participant_type"]),
        ]
