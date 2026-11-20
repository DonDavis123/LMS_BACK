"""Clear the cached suspension answer whenever a company row changes.

Suspending or reactivating a company (``set_status``) saves the row, which
clears the entry, so the change applies on the very next request.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from src.modules.shared.infrastructure.caching import auth_cache

from .django_company_model import DjangoCompanyModel


@receiver(
    post_save, sender=DjangoCompanyModel, dispatch_uid="auth_cache_company_saved"
)
@receiver(
    post_delete, sender=DjangoCompanyModel, dispatch_uid="auth_cache_company_deleted"
)
def clear_cached_company_suspension(sender, instance, **kwargs):
    auth_cache.delete(auth_cache.company_suspension_key(instance.pk))
