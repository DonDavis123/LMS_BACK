from enum import Enum


class DealStage(str, Enum):
    NEW = "New"
    QUOTATION_SENT = "Quotation Sent"
    NEGOTIATION = "Negotiation"
    WON = "Won"
    LOST = "Lost"


# The single source of truth for default win probabilities (percent).
# Never hardcode these numbers anywhere else.
DEFAULT_PROBABILITY: dict[DealStage, int] = {
    DealStage.NEW: 10,
    DealStage.QUOTATION_SENT: 40,
    DealStage.NEGOTIATION: 70,
    DealStage.WON: 100,
    DealStage.LOST: 0,
}

CLOSED_STAGES = frozenset({DealStage.WON, DealStage.LOST})
