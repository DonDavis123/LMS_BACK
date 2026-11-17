"""Timeline helpers shared by the deal use cases."""
from decimal import Decimal

from src.modules.deals.domain.entities.deal import Deal
from src.modules.deals.domain.enums.deal_stage import DealStage
from src.modules.timeline.application.interfaces.timeline_recorder import (
    TimelineRecorder,
)

# TimelineEvent.message is a CharField(max_length=500).
MAX_MESSAGE_LENGTH = 500

TRACKED_FIELDS = (
    "name",
    "amount",
    "expected_close_date",
    "stage",
    "probability",
    "owner_id",
    "account_id",
    "contact_id",
    "description",
    "lost_reason",
)

FIELD_LABELS = {
    "name": "Name",
    "amount": "Amount",
    "expected_close_date": "Expected Close Date",
    "stage": "Stage",
    "probability": "Probability",
    "owner_id": "Deal Owner",
    "account_id": "Account",
    "contact_id": "Contact",
    "description": "Description",
    "lost_reason": "Lost Reason",
}


def clip(message: str) -> str:
    if len(message) <= MAX_MESSAGE_LENGTH:
        return message
    return message[: MAX_MESSAGE_LENGTH - 1] + "…"


def snapshot(deal: Deal) -> dict[str, object]:
    """JSON-safe-able values of the tracked fields (Decimal as a string)."""
    values = {field: getattr(deal, field) for field in TRACKED_FIELDS}
    amount = values["amount"]
    if isinstance(amount, Decimal):
        values["amount"] = f"{amount:.2f}"
    return values


def targets_for(deal: Deal) -> list[tuple[str, object]]:
    targets: list[tuple[str, object]] = [("DEAL", deal.id)]
    if deal.contact_id:
        targets.append(("CONTACT", deal.contact_id))
    if deal.account_id:
        targets.append(("ACCOUNT", deal.account_id))
    return targets


def record_stage_events(
    recorder: TimelineRecorder,
    deal: Deal,
    from_stage: DealStage | None,
    actor_id,
) -> None:
    """DEAL_STAGE_CHANGED, plus DEAL_WON / DEAL_LOST when the deal closes."""
    if from_stage is not None and deal.stage is from_stage:
        return

    targets = targets_for(deal)
    base = {"deal_id": str(deal.id), "name": deal.name}

    if from_stage is not None:
        recorder.record(
            event_type="DEAL_STAGE_CHANGED",
            actor_id=actor_id,
            message=clip(
                f"Deal {deal.name} moved from {from_stage.value} "
                f"to {deal.stage.value}."
            ),
            metadata={
                **base,
                "from_stage": from_stage.value,
                "to_stage": deal.stage.value,
                "probability": deal.probability,
            },
            targets=targets,
        )

    if deal.stage is DealStage.WON:
        recorder.record(
            event_type="DEAL_WON",
            actor_id=actor_id,
            message=clip(f"Deal {deal.name} was won."),
            metadata={**base, "amount": f"{deal.amount:.2f}"},
            targets=targets,
        )
    elif deal.stage is DealStage.LOST:
        recorder.record(
            event_type="DEAL_LOST",
            actor_id=actor_id,
            message=clip(f"Deal {deal.name} was lost."),
            metadata={
                **base,
                "amount": f"{deal.amount:.2f}",
                "lost_reason": deal.lost_reason,
            },
            targets=targets,
        )
