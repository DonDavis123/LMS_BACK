from django.db import models
from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.accounts.infrastructure.persistence.django_account_document_model import (
    DjangoAccountDocumentModel,
)

__all__ = ["DjangoAccountModel", "DjangoAccountDocumentModel"]

# Create your models here.
