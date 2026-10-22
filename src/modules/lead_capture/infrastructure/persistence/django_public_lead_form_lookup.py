from src.modules.lead_capture.application.interfaces.public_lead_form_lookup import (
    PublicFormTarget,
    PublicLeadFormLookup,
)
from src.modules.lead_capture.infrastructure.persistence.django_lead_form_model import (
    DjangoLeadFormModel,
)


class DjangoPublicLeadFormLookup(PublicLeadFormLookup):
    def find_by_token(self, public_token: str) -> PublicFormTarget | None:
        # NOTE: this is the ONLY place tenant scoping is bypassed. The query
        # is deliberately not pinned to a company because the company is
        # exactly what we are looking up. It returns nothing but the
        # company id and name; all later work is company-pinned.
        row = (
            DjangoLeadFormModel.objects.filter(public_token=public_token)
            .values("company_id", "company__name")
            .first()
        )
        if row is None:
            return None
        return PublicFormTarget(
            company_id=row["company_id"], company_name=row["company__name"]
        )
