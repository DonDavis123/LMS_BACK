from uuid import UUID

from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.contacts.domain.entities.contact import Contact

from .django_contact_model import DjangoContactModel


class DjangoContactRepository(ContactRepository):

    def save(self, contact: Contact) -> Contact:
        model, created = DjangoContactModel.objects.update_or_create(
            id=contact.id,
            defaults={
                "account_id": contact.account_id,
                "contact_owner_id": contact.contact_owner_id,
                "name": contact.name,
                "email": contact.email,
                "secondary_email": contact.secondary_email,
                "phone": contact.phone,
                "other_phone": contact.other_phone,
                "mobile": contact.mobile,
                "home_phone": contact.home_phone,
                "assistant_phone": contact.assistant_phone,
                "title": contact.title,
                "department": contact.department,
                "lead_source": contact.lead_source,
                "vendor_name": contact.vendor_name,
                "date_of_birth": contact.date_of_birth,
                "assistant": contact.assistant,
                "email_opt_out": contact.email_opt_out,
                "reporting_to_id": contact.reporting_to_id,
                "mailing_address": contact.mailing_address,
                "mailing_city": contact.mailing_city,
                "mailing_state": contact.mailing_state,
                "mailing_country": contact.mailing_country,
                "mailing_postal_code": contact.mailing_postal_code,
                "other_address": contact.other_address,
                "description": contact.description,
                "created_by_id": contact.created_by_id,
                "created_at": contact.created_at,
                "modified_by_id": contact.modified_by_id,
                "updated_at": contact.updated_at,
            },
        )

        return self._to_domain(model)

    def get_by_id(self, contact_id: UUID) -> Contact | None:
        try:
            model = DjangoContactModel.objects.get(
                id=contact_id,
            )
        except DjangoContactModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def get_all(self) -> list[Contact]:
        models = DjangoContactModel.objects.all()

        return [
            self._to_domain(model)
            for model in models
        ]

    @staticmethod
    def _to_domain(model: DjangoContactModel) -> Contact:
        return Contact(
            id=model.id,
            account_id=model.account_id,
            contact_owner_id=model.contact_owner_id,
            name=model.name,
            email=model.email,
            secondary_email=model.secondary_email,
            phone=model.phone,
            other_phone=model.other_phone,
            mobile=model.mobile,
            home_phone=model.home_phone,
            assistant_phone=model.assistant_phone,
            title=model.title,
            department=model.department,
            lead_source=model.lead_source,
            vendor_name=model.vendor_name,
            date_of_birth=model.date_of_birth,
            assistant=model.assistant,
            email_opt_out=model.email_opt_out,
            reporting_to_id=model.reporting_to_id,
            mailing_address=model.mailing_address,
            mailing_city=model.mailing_city,
            mailing_state=model.mailing_state,
            mailing_country=model.mailing_country,
            mailing_postal_code=model.mailing_postal_code,
            other_address=model.other_address,
            description=model.description,
            created_by_id=model.created_by_id,
            created_at=model.created_at,
            modified_by_id=model.modified_by_id,
            updated_at=model.updated_at,
        )