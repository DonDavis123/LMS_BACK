from datetime import datetime, timedelta, timezone

from src.modules.deals.application.dto.deal_board import (
    DealBoardColumnDTO,
    DealBoardQuery,
)
from src.modules.deals.application.interfaces.deal_repository import DealRepository

# Cards returned per column; ``count`` / totals always cover every deal.
BOARD_CARD_LIMIT = 50
MIN_CLOSED_WITHIN_DAYS = 1
MAX_CLOSED_WITHIN_DAYS = 3650


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GetDealBoardUseCase:

    def __init__(self, deal_repository: DealRepository):
        self.deal_repository = deal_repository

    def execute(
        self,
        query: DealBoardQuery,
        now: datetime | None = None,
    ) -> list[DealBoardColumnDTO]:
        if not (
            MIN_CLOSED_WITHIN_DAYS <= query.closed_within_days <= MAX_CLOSED_WITHIN_DAYS
        ):
            raise ValueError(
                "closed_within_days must be between "
                f"{MIN_CLOSED_WITHIN_DAYS} and {MAX_CLOSED_WITHIN_DAYS}."
            )

        if (
            query.expected_close_from is not None
            and query.expected_close_to is not None
            and query.expected_close_from > query.expected_close_to
        ):
            raise ValueError(
                "expected_close_from must not be after expected_close_to."
            )

        search = query.search.strip() if query.search else None

        if search != query.search:
            query = DealBoardQuery(
                owner_id=query.owner_id,
                expected_close_from=query.expected_close_from,
                expected_close_to=query.expected_close_to,
                search=search or None,
                closed_within_days=query.closed_within_days,
            )

        now = now or _utcnow()
        closed_since = now - timedelta(days=query.closed_within_days)

        return self.deal_repository.get_board(query, closed_since, BOARD_CARD_LIMIT)
