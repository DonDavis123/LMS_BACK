from enum import Enum


class CallType(str, Enum):
    OUTBOUND = "Outbound"
    INBOUND = "Inbound"
