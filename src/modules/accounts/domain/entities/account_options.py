from enum import Enum

# Starting options for the customisable Account dropdowns. These are only seed
# data: after a company's first read, each company edits its own copy (see the
# picklists module). Kept separate from Leads / Contacts so changing one
# module's defaults never affects another.


class AccountType(str, Enum):
    NONE = "None"
    ANALYST = "Analyst"
    COMPETITOR = "Competitor"
    CUSTOMER = "Customer"
    DISTRIBUTOR = "Distributor"
    INTEGRATOR = "Integrator"
    INVESTOR = "Investor"
    OTHER = "Other"
    PARTNER = "Partner"
    PRESS = "Press"
    PROSPECT = "Prospect"
    RESELLER = "Reseller"
    SUPPLIER = "Supplier"
    VENDOR = "Vendor"


class AccountIndustry(str, Enum):
    NONE = "None"
    ASP_APPLICATION_SERVICE_PROVIDER = "ASP (Application Service Provider)"
    DATA_TELECOM_OEM = "Data/Telecom OEM"
    ERP_ENTERPRISE_RESOURCE_PLANNING = "ERP (Enterprise Resource Planning)"
    GOVERNMENT_MILITARY = "Government/Military"
    LARGE_ENTERPRISE = "Large Enterprise"
    MANAGEMENT = "Management"
    ISV = "ISV"
    MSP_MANAGEMENT_SERVICE_PROVIDER = "MSP (Management Service Provider)"
    NETWORK_EQUIPMENT_ENTERPRISE = "Network Equipment Enterprise"
    NON_MANAGEMENT_ISV = "Non-management ISV"
    OPTICAL_NETWORKING = "Optical Networking"
    SERVICE_PROVIDER = "Service Provider"
    SMALL_MEDIUM_ENTERPRISE = "Small/Medium Enterprise"
    STORAGE_EQUIPMENT = "Storage Equipment"
    STORAGE_SERVICE_PROVIDER = "Storage Service Provider"
    SYSTEMS_INTEGRATOR = "Systems Integrator"
    WIRELESS_INDUSTRY = "Wireless Industry"
    ERP = "ERP"
    MANAGEMENT_ISV = "Management ISV"


class AccountRating(str, Enum):
    NONE = "None"
    ACQUIRED = "Acquired"
    ACTIVE = "Active"
    MARKET_FAILED = "Market Failed"
    PROJECT_CANCELLED = "Project Cancelled"
    SHUT_DOWN = "Shut Down"


class AccountOwnership(str, Enum):
    NONE = "None"
    OTHER = "Other"
    PRIVATE = "Private"
    PUBLIC = "Public"
    SUBSIDIARY = "Subsidiary"
    PARTNERSHIP = "Partnership"
    GOVERNMENT = "Government"
    PRIVATELY_HELD = "Privately Held"
    PUBLIC_COMPANY = "Public Company"
