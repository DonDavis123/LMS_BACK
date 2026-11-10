from src.modules.companies.infrastructure.persistence.django_company_model import (
    DjangoCompanyModel,
)
from src.modules.users.domain.entities.user import User

from .serializers.get_current_user import CurrentUserSerializer


def build_current_user_payload(user: User) -> dict:
    company = None
    if user.company_id is not None:
        company_model = DjangoCompanyModel.objects.filter(
            id=user.company_id,
        ).first()
        if company_model is not None:
            company = {
                "id": company_model.id,
                "name": company_model.name,
                "status": company_model.status,
            }

    return CurrentUserSerializer({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role.value,
        "google_email": user.google_email,
        "mail_account_email": user.mail_account_email,
        "company": company,
    }).data
