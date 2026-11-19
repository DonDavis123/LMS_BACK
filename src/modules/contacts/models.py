from django.db import models
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)

from src.modules.contacts.infrastructure.persistence.django_contact_summary_model import (
    DjangoContactSummaryModel,
)

__all__ = ["DjangoContactModel", "DjangoContactSummaryModel"]

# Create your models here.
