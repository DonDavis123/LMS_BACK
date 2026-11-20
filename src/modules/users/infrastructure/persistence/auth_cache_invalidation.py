"""Clear the cached authentication user whenever a user row changes.

Every write in the project goes through ``Model.save()`` / ``delete()``, so
these signals cover role changes, blocking, soft delete, password resets and
profile edits. (A bulk ``QuerySet.update()`` sends no signal; the short
``AUTH_CACHE_TTL_SECONDS`` bounds how long such a change could stay hidden.)
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from src.modules.shared.infrastructure.caching import auth_cache

from .models import User


@receiver(post_save, sender=User, dispatch_uid="auth_cache_user_saved")
@receiver(post_delete, sender=User, dispatch_uid="auth_cache_user_deleted")
def clear_cached_user(sender, instance, **kwargs):
    auth_cache.delete(auth_cache.user_key(instance.pk))
