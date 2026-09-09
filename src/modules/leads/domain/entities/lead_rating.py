from enum import Enum


class LeadRating(str, Enum):
    NONE = "None"
    ACQUIRED = "Acquired"
    ACTIVE = "Active"
    MARKET_FAILED = "Market Failed"
    PROJECT_CANCELLED = "Project Cancelled"
    SHUT_DOWN = "Shut Down"