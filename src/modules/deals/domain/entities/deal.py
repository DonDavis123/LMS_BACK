from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from ..enums.deal_stage import CLOSED_STAGES, DEFAULT_PROBABILITY, DealStage

MAX_NAME_LENGTH = 255
MAX_LOST_REASON_LENGTH = 255
# DecimalField(max_digits=14, decimal_places=2) holds at most 12 integer digits.
MAX_AMOUNT = Decimal("10") ** 12


def _now() -> datetime:
    return datetime.now(timezone.utc)


def validate_probability(value: object) -> int:
    """Probability must be a real integer between 0 and 100 (bool is rejected)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Probability must be an integer between 0 and 100.")
    if value < 0 or value > 100:
        raise ValueError("Probability must be between 0 and 100.")
    return value


def validate_amount(value: object) -> Decimal:
    if isinstance(value, float):
        raise ValueError("Amount must be a decimal number, not a float.")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Amount must be a valid number.")
    if not amount.is_finite():
        raise ValueError("Amount must be a valid number.")
    if amount < 0:
        raise ValueError("Amount must be greater than or equal to 0.")
    if amount >= MAX_AMOUNT:
        raise ValueError("Amount is too large.")
    return amount


def validate_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Deal name is required.")
    name = value.strip()
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Deal name must be at most {MAX_NAME_LENGTH} characters.")
    return name


@dataclass
class Deal:
    id: UUID
    name: str
    amount: Decimal
    expected_close_date: date | None
    stage: DealStage
    probability: int
    owner_id: UUID
    account_id: UUID | None
    contact_id: UUID | None
    source_lead_id: UUID | None
    lead_source: str | None
    description: str | None
    lost_reason: str | None
    closed_at: datetime | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    @property
    def is_closed(self) -> bool:
        return self.stage in CLOSED_STAGES

    def soft_delete(self) -> None:
        if self.is_deleted:
            raise ValueError("Deal is already deleted.")

        self.is_deleted = True

    def set_probability(self, probability: object) -> None:
        """Override the probability of an open deal (closed deals are fixed)."""
        value = validate_probability(probability)
        if self.is_closed and value != DEFAULT_PROBABILITY[self.stage]:
            raise ValueError(
                f"Probability of a {self.stage.value} deal is fixed at "
                f"{DEFAULT_PROBABILITY[self.stage]}."
            )
        self.probability = value

    def set_lost_reason(self, lost_reason: str | None) -> None:
        if self.stage is not DealStage.LOST:
            raise ValueError("A lost reason can only be set on a Lost deal.")
        self.lost_reason = self._validate_lost_reason(lost_reason)

    @staticmethod
    def _validate_lost_reason(lost_reason: object) -> str:
        if not isinstance(lost_reason, str) or not lost_reason.strip():
            raise ValueError("A lost reason is required when a deal is Lost.")
        reason = lost_reason.strip()
        if len(reason) > MAX_LOST_REASON_LENGTH:
            raise ValueError(
                f"Lost reason must be at most {MAX_LOST_REASON_LENGTH} characters."
            )
        return reason

    def move_to_stage(
        self,
        stage: "DealStage | str",
        probability: object = None,
        lost_reason: str | None = None,
        now: datetime | None = None,
    ) -> None:
        """Move the deal to ``stage`` applying the stage rules.

        * Open stages: probability = explicit value, else the stage default
          (a deal that is already in that stage keeps its probability).
          Leaving Won/Lost clears ``closed_at`` and ``lost_reason``.
        * Won: probability 100, ``closed_at`` set, ``lost_reason`` cleared.
        * Lost: probability 0, non-blank ``lost_reason`` required,
          ``closed_at`` set.

        Nothing is changed when validation fails.
        """
        try:
            target = stage if isinstance(stage, DealStage) else DealStage(stage)
        except ValueError:
            allowed = ", ".join(s.value for s in DealStage)
            raise ValueError(f"Invalid stage. Allowed stages: {allowed}.")

        explicit = None if probability is None else validate_probability(probability)

        reason = None
        if target is DealStage.LOST:
            reason = self._validate_lost_reason(
                lost_reason if lost_reason is not None else self.lost_reason
            )

        moment = now or _now()
        unchanged = target is self.stage

        if target is DealStage.WON:
            new_probability = DEFAULT_PROBABILITY[DealStage.WON]
        elif target is DealStage.LOST:
            new_probability = DEFAULT_PROBABILITY[DealStage.LOST]
        elif explicit is not None:
            new_probability = explicit
        elif unchanged:
            new_probability = self.probability
        else:
            new_probability = DEFAULT_PROBABILITY[target]

        self.stage = target
        self.probability = new_probability

        if target in CLOSED_STAGES:
            if not unchanged or self.closed_at is None:
                self.closed_at = moment
            self.lost_reason = reason
        else:
            self.closed_at = None
            self.lost_reason = None

        self.updated_at = moment

    @classmethod
    def create(
        cls,
        name: str,
        owner_id: UUID,
        created_by_id: UUID,
        amount: Decimal = Decimal("0"),
        expected_close_date: date | None = None,
        stage: "DealStage | str" = DealStage.NEW,
        probability: object = None,
        account_id: UUID | None = None,
        contact_id: UUID | None = None,
        source_lead_id: UUID | None = None,
        lead_source: str | None = None,
        description: str | None = None,
        lost_reason: str | None = None,
    ) -> "Deal":
        now = _now()

        deal = cls(
            id=uuid4(),
            name=validate_name(name),
            amount=validate_amount(amount),
            expected_close_date=expected_close_date,
            stage=DealStage.NEW,
            probability=DEFAULT_PROBABILITY[DealStage.NEW],
            owner_id=owner_id,
            account_id=account_id,
            contact_id=contact_id,
            source_lead_id=source_lead_id,
            lead_source=lead_source,
            description=description,
            lost_reason=None,
            closed_at=None,
            created_by_id=created_by_id,
            created_at=now,
            updated_at=now,
            is_deleted=False,
        )
        deal.move_to_stage(stage, probability, lost_reason, now=now)
        return deal
