from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.picklists.infrastructure.persistence.django_picklist_option_model import (
    DjangoPicklistOptionModel,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

PICKLIST = "/api/picklists/contacts/lead_source/"


def make_contact(company, owner, name, **extra):
    now = timezone.now()
    return DjangoContactModel.objects.create(
        company=company,
        contact_owner=owner,
        name=name,
        created_by=owner,
        created_at=now,
        modified_by=owner,
        updated_at=now,
        **extra,
    )


class ContactDropdownUpdateTests(APITestCase):
    def setUp(self):
        self.company_a = make_company("Contact Pick A", "cpick-a")
        self.company_b = make_company("Contact Pick B", "cpick-b")
        self.super_a = make_user(self.company_a, User.Role.SUPERADMIN, "cpick-super-a@example.com")
        self.admin_a = make_user(self.company_a, User.Role.ADMIN, "cpick-admin-a@example.com")
        self.super_b = make_user(self.company_b, User.Role.SUPERADMIN, "cpick-super-b@example.com")
        self.sa = authenticated_client(self.super_a)
        self.adm = authenticated_client(self.admin_a)
        self.sb = authenticated_client(self.super_b)

    def update_url(self, contact):
        return f"/api/contacts/{contact.id}/update/"

    def option_id(self, client, value):
        response = client.get(PICKLIST, {"include_inactive": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return next(o["id"] for o in response.data["options"] if o["value"] == value)

    def test_company_gets_default_contact_lead_sources(self):
        response = self.adm.get(PICKLIST)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        values = [o["value"] for o in response.data["options"]]
        self.assertEqual(values[0], "None")
        self.assertIn("Cold Call", values)

    def test_leads_and_contacts_options_are_independent(self):
        self.sa.post(PICKLIST + "create/", {"value": "Roadshow"}, format="json")
        leads = self.sa.get("/api/picklists/leads/lead_source/")
        self.assertNotIn("Roadshow", [o["value"] for o in leads.data["options"]])

    def test_update_accepts_active_option_and_normalises_case(self):
        contact = make_contact(self.company_a, self.super_a, "Ann")
        response = self.sa.patch(self.update_url(contact), {"lead_source": "web research"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        contact.refresh_from_db()
        self.assertEqual(contact.lead_source, "Web Research")

    def test_update_accepts_company_custom_option(self):
        self.sa.post(PICKLIST + "create/", {"value": "Roadshow"}, format="json")
        contact = make_contact(self.company_a, self.super_a, "Ann")
        response = self.sa.patch(self.update_url(contact), {"lead_source": "Roadshow"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        contact.refresh_from_db()
        self.assertEqual(contact.lead_source, "Roadshow")

    def test_update_rejects_unknown_value(self):
        contact = make_contact(self.company_a, self.super_a, "Ann")
        response = self.sa.patch(self.update_url(contact), {"lead_source": "Carrier Pigeon"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        contact.refresh_from_db()
        self.assertIsNone(contact.lead_source)

    def test_other_company_option_is_not_valid(self):
        self.sb.post(PICKLIST + "create/", {"value": "Only B"}, format="json")
        contact = make_contact(self.company_a, self.super_a, "Ann")
        response = self.sa.patch(self.update_url(contact), {"lead_source": "Only B"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hidden_option_rejected_but_kept_when_unchanged(self):
        contact = make_contact(self.company_a, self.super_a, "Ann", lead_source="Chat")
        option_id = self.option_id(self.sa, "Chat")
        hide = self.sa.patch(f"/api/picklists/options/{option_id}/update/", {"is_active": False}, format="json")
        self.assertEqual(hide.status_code, status.HTTP_200_OK, hide.content)

        keep = self.sa.patch(
            self.update_url(contact), {"lead_source": "Chat", "title": "CTO"}, format="json"
        )
        self.assertEqual(keep.status_code, status.HTTP_200_OK, keep.content)

        other = make_contact(self.company_a, self.super_a, "Bob")
        rejected = self.sa.patch(self.update_url(other), {"lead_source": "Chat"}, format="json")
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

    def test_blank_lead_source_becomes_none_option(self):
        contact = make_contact(self.company_a, self.super_a, "Ann", lead_source="Chat")
        response = self.sa.patch(self.update_url(contact), {"lead_source": ""}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        contact.refresh_from_db()
        self.assertEqual(contact.lead_source, "None")

    def test_update_without_lead_source_leaves_it_alone(self):
        contact = make_contact(self.company_a, self.super_a, "Ann", lead_source="Chat")
        response = self.sa.patch(self.update_url(contact), {"title": "CTO"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        contact.refresh_from_db()
        self.assertEqual(contact.lead_source, "Chat")
        self.assertEqual(contact.title, "CTO")

    def test_renaming_option_moves_contacts_of_that_company_only(self):
        mine = make_contact(self.company_a, self.super_a, "Ann", lead_source="Chat")
        theirs = make_contact(self.company_b, self.super_b, "Zed", lead_source="Chat")
        option_id = self.option_id(self.sa, "Chat")
        response = self.sa.patch(f"/api/picklists/options/{option_id}/update/", {"value": "Live Chat"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertEqual(mine.lead_source, "Live Chat")
        self.assertEqual(theirs.lead_source, "Chat")

    def test_deleting_option_in_use_needs_replacement(self):
        make_contact(self.company_a, self.super_a, "Ann", lead_source="Chat")
        option_id = self.option_id(self.sa, "Chat")
        response = self.sa.delete(f"/api/picklists/options/{option_id}/delete/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT, response.content)
        self.assertEqual(response.data["usage_count"], 1)

    def test_admin_cannot_edit_options(self):
        response = self.adm.post(PICKLIST + "create/", {"value": "Nope"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
