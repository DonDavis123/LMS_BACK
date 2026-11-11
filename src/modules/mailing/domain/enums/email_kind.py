from enum import Enum


class EmailKind(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
