from enum import Enum


class ContactLeadSource(str, Enum):
    """Starting options for Contacts -> Lead Source.

    Only seed data: after a company's first read each company edits its own
    copy of these options (see the picklists module). Kept separate from the
    Leads enum so changing one module's defaults never affects the other.
    """

    NONE = "None"
    ADVERTISEMENT = "Advertisement"
    COLD_CALL = "Cold Call"
    EMPLOYEE_REFERRAL = "Employee Referral"
    EXTERNAL_REFERRAL = "External Referral"
    ONLINE_STORE = "Online Store"
    PARTNER = "Partner"
    PUBLIC_RELATIONS = "Public Relations"
    SALES_EMAIL_ALIAS = "Sales Email Alias"
    SEMINAR_PARTNER = "Seminar Partner"
    INTERNAL_SEMINAR = "Internal Seminar"
    TRADE_SHOW = "Trade Show"
    WEB_DOWNLOAD = "Web Download"
    WEB_RESEARCH = "Web Research"
    CHAT = "Chat"
    X_TWITTER = "X (Twitter)"
    FACEBOOK = "Facebook"
    OTHER = "Other"
