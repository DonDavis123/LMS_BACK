from enum import Enum


class AssignmentMode(str, Enum):
    SINGLE_OWNER = "SINGLE_OWNER"
    ROTATION = "ROTATION"
