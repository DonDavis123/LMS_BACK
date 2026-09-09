from collections.abc import Callable
from typing import TypeVar

from django.db import transaction

from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)


T = TypeVar("T")


class DjangoTransactionManager(TransactionManager):

    def execute(self, operation: Callable[[], T]) -> T:

        with transaction.atomic():
            return operation()