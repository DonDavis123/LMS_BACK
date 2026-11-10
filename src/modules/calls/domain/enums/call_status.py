from enum import Enum


class CallStatus(str, Enum):
    """Lifecycle of a call.

    PLANNED    a call scheduled for a (usually future) date; no outcome yet.
    COMPLETED  a call that happened and was logged with an outcome.
    MISSED     a planned call that did not take place.
    """

    PLANNED = "Planned"
    COMPLETED = "Completed"
    MISSED = "Missed"
