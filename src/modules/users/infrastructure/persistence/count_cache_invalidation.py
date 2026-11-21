"""Bump the cached list totals that depend on a user's name.

The contacts list filters on the owner's name and the calls list searches it,
so renaming, deleting or moving a user changes those totals. Routine saves
that only touch other columns (``last_login`` on every login, for example) are
ignored.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from src.modules.shared.infrastructure.caching import count_cache

from .models import User

_NAME_FIELDS = {"name", "is_deleted", "company", "company_id"}


@receiver(post_save, sender=User, dispatch_uid="count_cache_user_saved")
def bump_on_user_saved(sender, instance, created, update_fields=None, **kwargs):
    if created:
        return  # a new user owns nothing yet
    if update_fields is not None and not (set(update_fields) & _NAME_FIELDS):
        return
    count_cache.bump_affected(
        getattr(instance, "company_id", None), count_cache.USERS
    )


@receiver(post_delete, sender=User, dispatch_uid="count_cache_user_deleted")
def bump_on_user_deleted(sender, instance, **kwargs):
    count_cache.bump_affected(
        getattr(instance, "company_id", None), count_cache.USERS
    )
