from django.db import models
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)

from src.modules.leads.infrastructure.persistence.django_lead_import_job_model import (
    LeadImportJob,
)

from src.modules.leads.infrastructure.persistence.django_lead_summary_model import (
    DjangoLeadSummaryModel,
)

__all__ = ["DjangoLeadModel", "LeadImportJob", "DjangoLeadSummaryModel"]

# Create your models here.
