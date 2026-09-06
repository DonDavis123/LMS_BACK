from enum import Enum


class LeadSource(str, Enum):
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