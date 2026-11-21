"""Bump the cached list total whenever a contact row changes.

``Model.save()`` and ``Model.delete()`` (also ``QuerySet.delete()``, which
sends ``post_delete`` per row) cover create, update, soft delete and lead
conversion. ``bulk_create``, ``bulk_update`` and ``QuerySet.update()`` send no
signal, so the repositories call ``count_cache.bump_affected`` themselves after
each of those. See ``shared/infrastructure/caching/count_cache.py``.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from src.modules.shared.infrastructure.caching import count_cache

from .django_contact_model import DjangoContactModel


@receiver(post_save, sender=DjangoContactModel, dispatch_uid="count_cache_contact_saved")
@receiver(post_delete, sender=DjangoContactModel, dispatch_uid="count_cache_contact_deleted")
def bump_contacts_count_version(sender, instance, **kwargs):
    # Skipped silently when the row has no company.
    count_cache.bump_affected(
        getattr(instance, "company_id", None), count_cache.CONTACTS
    )
