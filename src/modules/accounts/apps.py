from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.modules.accounts"

    def ready(self):
        # Registers the signals that bump the cached list total when a row
        # is saved or deleted.
        from src.modules.accounts.infrastructure.persistence import (  # noqa: F401
            count_cache_invalidation,
        )
