from django.db import models
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)

from src.modules.leads.infrastructure.persistence.django_lead_import_job_model import (
    LeadImportJob,
)

__all__ = ["DjangoLeadModel", "LeadImportJob"]

# Create your models here.
