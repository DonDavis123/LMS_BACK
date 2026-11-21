from django.apps import AppConfig


class ContactsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.modules.contacts"

    def ready(self):
        # Registers the signals that bump the cached list total when a row
        # is saved or deleted.
        from src.modules.contacts.infrastructure.persistence import (  # noqa: F401
            count_cache_invalidation,
        )
