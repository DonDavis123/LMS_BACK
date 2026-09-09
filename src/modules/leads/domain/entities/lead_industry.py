from enum import Enum


class LeadIndustry(str, Enum):
    NONE = "None"
    ASP = "ASP (Application Service Provider)"
    DATA_TELECOM_OEM = "Data/Telecom OEM"
    ERP_ENTERPRISE_RESOURCE_PLANNING = "ERP (Enterprise Resource Planning)"
    GOVERNMENT_MILITARY = "Government/Military"
    LARGE_ENTERPRISE = "Large Enterprise"
    MANAGEMENT = "Management"
    ISV = "ISV"
    MSP = "MSP (Management Service Provider)"
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