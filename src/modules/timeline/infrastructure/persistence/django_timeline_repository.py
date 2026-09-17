from datetime import datetime
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction

from src.modules.accounts.infrastructure.persistence.django_account_model import DjangoAccountModel
from src.modules.contacts.infrastructure.persistence.django_contact_model import DjangoContactModel
from src.modules.leads.infrastructure.persistence.django_lead_model import DjangoLeadModel
from src.modules.timeline.application.interfaces.timeline_repository import TimelineRepository
from src.modules.timeline.infrastructure.persistence.models import TimelineEvent, TimelineEventTarget


class DjangoTimelineRepository(TimelineRepository):
    def record(
        self,
        *,
        event_type: str,
        actor_id: UUID,
        message: str,
        metadata: dict,
        targets: list[tuple[str, UUID]],
        created_at: datetime | None = None,
    ) -> None:
        event_kwargs = {
            "event_type": event_type,
            "actor_id": actor_id,
            "message": message,
            "metadata": metadata,
        }
        if created_at is not None:
            event_kwargs["created_at"] = created_at

        with transaction.atomic():
            event = TimelineEvent.objects.create(**event_kwargs)
            TimelineEventTarget.objects.bulk_create([
                TimelineEventTarget(
                    event=event,
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
                for entity_type, entity_id in targets
            ])

    def get_for_entity(self, entity_type: str, entity_id: UUID) -> list[dict]:
        rows = (
            TimelineEventTarget.objects
            .filter(entity_type=entity_type, entity_id=entity_id)
            .select_related("event", "event__actor")
            .prefetch_related("event__targets")
            .order_by("-event__created_at", "-event__id")
        )
        result = []
        seen = set()
        for row in rows:
            if row.event_id in seen:
                continue
            seen.add(row.event_id)
            event = row.event
            result.append({
                "id": event.id,
                "event_type": event.event_type,
                "actor": {
                    "id": event.actor_id,
                    "name": getattr(event.actor, "name", event.actor.email),
                },
                "message": event.message,
                "metadata": event.metadata,
                "created_at": event.created_at,
                "targets": [
                    {"entity_type": target.entity_type, "entity_id": target.entity_id}
                    for target in event.targets.all()
                ],
            })
        return result

    def entity_exists(self, entity_type: str, entity_id: UUID) -> bool:
        models = {
            "LEAD": DjangoLeadModel,
            "CONTACT": DjangoContactModel,
            "ACCOUNT": DjangoAccountModel,
        }
        model = models.get(entity_type)
        if model is None:
            raise ValueError("Unsupported timeline entity type.")
        return model.objects.filter(id=entity_id, is_deleted=False).exists()
