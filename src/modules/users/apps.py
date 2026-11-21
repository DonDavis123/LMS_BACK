from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.modules.users"

    def ready(self):
        # Registers the signal that clears the cached authentication user
        # when a user row is saved or deleted.
        from src.modules.users.infrastructure.persistence import (  # noqa: F401
            auth_cache_invalidation,
        )

        # Same for the list totals that depend on a user's name.
        from src.modules.users.infrastructure.persistence import (  # noqa: F401
            count_cache_invalidation,
        )
