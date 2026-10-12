from uuid import UUID

from .django_company_model import DjangoCompanyModel


def get_active_company_ids() -> list[UUID]:
    """Ids of companies that are ACTIVE (not SUSPENDED or ONBOARDING)."""
    return list(
        DjangoCompanyModel.objects.filter(
            status=DjangoCompanyModel.Status.ACTIVE,
        )
        .order_by("created_at", "id")
        .values_list("id", flat=True)
    )
