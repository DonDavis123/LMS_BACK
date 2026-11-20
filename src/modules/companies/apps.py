from django.apps import AppConfig


class CompaniesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.modules.companies"

    def ready(self):
        # Registers the signal that clears the cached suspension answer
        # when a company row is saved or deleted.
        from src.modules.companies.infrastructure.persistence import (  # noqa: F401
            company_cache_invalidation,
        )
