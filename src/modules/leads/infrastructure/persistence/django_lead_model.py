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

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=255,
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
    )

    lead_source = models.CharField(
        max_length=100,
        choices=LeadSource.choices,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="leads",
    )

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