import uuid

from django.conf import settings
from django.db import models


class DjangoLeadModel(models.Model):

    class LeadSource(models.TextChoices):
        NONE = "None", "None"
        ADVERTISEMENT = "Advertisement", "Advertisement"
        COLD_CALL = "Cold Call", "Cold Call"
        EMPLOYEE_REFERRAL = "Employee Referral", "Employee Referral"
        EXTERNAL_REFERRAL = "External Referral", "External Referral"
        ONLINE_STORE = "Online Store", "Online Store"
        PARTNER = "Partner", "Partner"
        PUBLIC_RELATIONS = "Public Relations", "Public Relations"
        SALES_EMAIL_ALIAS = "Sales Email Alias", "Sales Email Alias"
        SEMINAR_PARTNER = "Seminar Partner", "Seminar Partner"
        INTERNAL_SEMINAR = "Internal Seminar", "Internal Seminar"
        TRADE_SHOW = "Trade Show", "Trade Show"
        WEB_DOWNLOAD = "Web Download", "Web Download"
        WEB_RESEARCH = "Web Research", "Web Research"
        CHAT = "Chat", "Chat"
        X_TWITTER = "X (Twitter)", "X (Twitter)"
        FACEBOOK = "Facebook", "Facebook"

    class LeadStatus(models.TextChoices):
        NONE = "None", "None"
        ATTEMPTED_TO_CONTACT = (
            "Attempted to Contact",
            "Attempted to Contact",
        )
        CONTACT_IN_FUTURE = (
            "Contact in Future",
            "Contact in Future",
        )
        CONTACTED = "Contacted", "Contacted"
        JUNK_LEAD = "Junk Lead", "Junk Lead"
        LOST_LEAD = "Lost Lead", "Lost Lead"
        NOT_CONTACTED = "Not Contacted", "Not Contacted"
        PRE_QUALIFIED = "Pre-Qualified", "Pre-Qualified"
        NOT_QUALIFIED = "Not Qualified", "Not Qualified"

    class LeadIndustry(models.TextChoices):
        NONE = "None", "None"
        ASP = (
            "ASP (Application Service Provider)",
            "ASP (Application Service Provider)",
        )
        DATA_TELECOM_OEM = (
            "Data/Telecom OEM",
            "Data/Telecom OEM",
        )
        ERP_ENTERPRISE_RESOURCE_PLANNING = (
            "ERP (Enterprise Resource Planning)",
            "ERP (Enterprise Resource Planning)",
        )
        GOVERNMENT_MILITARY = (
            "Government/Military",
            "Government/Military",
        )
        LARGE_ENTERPRISE = (
            "Large Enterprise",
            "Large Enterprise",
        )
        MANAGEMENT = "Management", "Management"
        ISV = "ISV", "ISV"
        MSP = (
            "MSP (Management Service Provider)",
            "MSP (Management Service Provider)",
        )
        NETWORK_EQUIPMENT_ENTERPRISE = (
            "Network Equipment Enterprise",
            "Network Equipment Enterprise",
        )
        NON_MANAGEMENT_ISV = (
            "Non-management ISV",
            "Non-management ISV",
        )
        OPTICAL_NETWORKING = (
            "Optical Networking",
            "Optical Networking",
        )
        SERVICE_PROVIDER = (
            "Service Provider",
            "Service Provider",
        )
        SMALL_MEDIUM_ENTERPRISE = (
            "Small/Medium Enterprise",
            "Small/Medium Enterprise",
        )
        STORAGE_EQUIPMENT = (
            "Storage Equipment",
            "Storage Equipment",
        )
        STORAGE_SERVICE_PROVIDER = (
            "Storage Service Provider",
            "Storage Service Provider",
        )
        SYSTEMS_INTEGRATOR = (
            "Systems Integrator",
            "Systems Integrator",
        )
        WIRELESS_INDUSTRY = (
            "Wireless Industry",
            "Wireless Industry",
        )
        ERP = "ERP", "ERP"
        MANAGEMENT_ISV = "Management ISV", "Management ISV"

    class LeadRating(models.TextChoices):
        NONE = "None", "None"
        ACQUIRED = "Acquired", "Acquired"
        ACTIVE = "Active", "Active"
        MARKET_FAILED = "Market Failed", "Market Failed"
        PROJECT_CANCELLED = (
            "Project Cancelled",
            "Project Cancelled",
        )
        SHUT_DOWN = "Shut Down", "Shut Down"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Basic information

    name = models.CharField(
        max_length=255,
    )

    title = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    company_name = models.CharField(
        max_length=255,
    )

    email = models.EmailField(
        blank=True,
        null=True,
    )

    mobile_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    # Lead information

    lead_source = models.CharField(
        max_length=100,
        choices=LeadSource.choices,
        default=LeadSource.NONE,
    )

    lead_status = models.CharField(
        max_length=100,
        choices=LeadStatus.choices,
        default=LeadStatus.NONE,
    )

    industry = models.CharField(
        max_length=150,
        choices=LeadIndustry.choices,
        default=LeadIndustry.NONE,
    )

    rating = models.CharField(
        max_length=100,
        choices=LeadRating.choices,
        default=LeadRating.NONE,
    )

    # Business information

    website = models.URLField(
        blank=True,
        null=True,
    )

    number_of_employees = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    annual_revenue = models.PositiveBigIntegerField(
        blank=True,
        null=True,
    )

    # Ownership

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="leads",
    )

    # Address

    address = models.CharField(
        max_length=500,
        blank=True,
        null=True,
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    state = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    postal_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    # Additional information

    description = models.TextField(
        blank=True,
        null=True,
    )

    # Backend controlled lifecycle

    is_deleted = models.BooleanField(
        default=False,
    )

    is_converted = models.BooleanField(
        default=False,
    )

    # Backend controlled timestamps

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "leads"

    def __str__(self):
        return self.name