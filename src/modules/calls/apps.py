from django.apps import AppConfig


class CallsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.modules.calls"

    def ready(self):
        # Registers the signal that removes a recording's audio file when
        # its row is deleted.
        from src.modules.calls.infrastructure.persistence import (  # noqa: F401
            recording_cleanup,
        )

        # Registers the signals that bump the cached list total when a call
        # is saved or deleted.
        from src.modules.calls.infrastructure.persistence import (  # noqa: F401
            count_cache_invalidation,
        )
