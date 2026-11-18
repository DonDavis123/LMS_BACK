"""Money rounding shared by the board and forecast read models."""
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def to_money(value: Decimal | int | str | None) -> Decimal:
    """Round to 2 decimals (half up). ``None`` (an empty SUM) becomes 0.00.

    Sums are computed unrounded in the database and rounded only here, at
    the very end, so rounding errors never accumulate.
    """
    if value is None:
        return Decimal("0.00")

    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
