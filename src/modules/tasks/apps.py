from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.modules.tasks"

    def ready(self):
        # Registers the signals that bump the cached list total when a row
        # is saved or deleted.
        from src.modules.tasks.infrastructure.persistence import (  # noqa: F401
            count_cache_invalidation,
        )
