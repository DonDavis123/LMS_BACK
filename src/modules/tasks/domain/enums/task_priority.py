from enum import Enum


class TaskPriority(str, Enum):
    HIGHEST = "Highest"
    HIGH = "High"
    NORMAL = "Normal"
    LOW = "Low"
    LOWEST = "Lowest"
