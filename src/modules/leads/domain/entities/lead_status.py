from enum import Enum


class LeadStatus(str, Enum):
    NONE = "None"
    ATTEMPTED_TO_CONTACT = "Attempted to Contact"
    CONTACT_IN_FUTURE = "Contact in Future"
    CONTACTED = "Contacted"
    JUNK_LEAD = "Junk Lead"
    LOST_LEAD = "Lost Lead"
    NOT_CONTACTED = "Not Contacted"
    PRE_QUALIFIED = "Pre-Qualified"
    NOT_QUALIFIED = "Not Qualified"