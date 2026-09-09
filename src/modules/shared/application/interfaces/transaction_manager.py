from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


class TransactionManager(ABC):

    @abstractmethod
    def execute(self, operation: Callable[[], T]) -> T:
        pass