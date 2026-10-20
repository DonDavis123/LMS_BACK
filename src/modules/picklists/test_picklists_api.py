import json

from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
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

LEADS = "/api/picklists/leads/"


def field_url(field):
    return f"{LEADS}{field}/"


def create_url(field):
    return f"{LEADS}{field}/create/"


def update_url(option_id):
    return f"/api/picklists/options/{option_id}/update/"


def delete_url(option_id):
    return f"/api/picklists/options/{option_id}/delete/"


class PicklistTestCase(APITestCase):
    """Company A and Company B, each with a SUPERADMIN; A also has an ADMIN."""

    def setUp(self):
        self.company_a = make_company("Company A", "pick-a")
        self.company_b = make_company("Company B", "pick-b")

        self.super_a = make_user(self.company_a, User.Role.SUPERADMIN, "pick-super-a@example.com")
        self.admin_a = make_user(self.company_a, User.Role.ADMIN, "pick-admin-a@example.com")
        self.super_b = make_user(self.company_b, User.Role.SUPERADMIN, "pick-super-b@example.com")

        self.sa = authenticated_client(self.super_a)
        self.adm = authenticated_client(self.admin_a)
        self.sb = authenticated_client(self.super_b)

    # helpers ---------------------------------------------------------
    def options(self, client, field, **params):
        response = client.get(field_url(field), params)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return response.data["options"]

    def values(self, client, field, **params):
        return [o["value"] for o in self.options(client, field, **params)]

    def option_id(self, client, field, value):
        for option in self.options(client, field, include_inactive="true"):
            if option["value"] == value:
                return option["id"]
        self.fail(f"{value!r} not found in {field}")

    def add(self, client, field, value):
        response = client.post(create_url(field), {"value": value}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        return response.data

    def make_lead(self, company, owner, name, **extra):
        return DjangoLeadModel.objects.create(
            company=company, owner=owner, name=name, **extra
        )

    def lead_payload(self, **extra):
        return {"name": "Lead One", "owner_id": str(self.super_a.id), **extra}


class ReadingOptionsTests(PicklistTestCase):
    def test_company_gets_the_built_in_defaults_on_first_read(self):
        self.assertFalse(DjangoPicklistOptionModel.objects.filter(company=self.company_a).exists())

        response = self.adm.get(LEADS)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        keys = [f["field"] for f in response.data["fields"]]
        self.assertEqual(keys, ["lead_source", "lead_status", "industry", "rating"])

        sources = self.values(self.adm, "lead_source")
        self.assertEqual(sources[0], "None")
        for expected in ("Advertisement", "Cold Call", "Other", "Facebook"):
            self.assertIn(expected, sources)

    def test_none_is_a_protected_system_option(self):
        none = next(o for o in self.options(self.sa, "rating") if o["value"] == "None")
        self.assertTrue(none["is_system"])

    def test_seeding_twice_does_not_duplicate(self):
        self.sa.get(LEADS)
        self.sa.get(LEADS)
        count = DjangoPicklistOptionModel.objects.filter(
            company=self.company_a, field="lead_source"
        ).count()
        self.assertEqual(count, len(set(self.values(self.sa, "lead_source"))))

    def test_unknown_module_or_field_is_404(self):
        self.assertEqual(self.sa.get("/api/picklists/nope/").status_code, 404)
        self.assertEqual(self.sa.get(field_url("nope")).status_code, 404)

    def test_unauthenticated_is_rejected(self):
        from rest_framework.test import APIClient

        self.assertEqual(APIClient().get(LEADS).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_platform_superadmin_has_no_access(self):
        platform = make_user(None, User.Role.PLATFORM_SUPERADMIN, "pick-platform@example.com")
        response = authenticated_client(platform).get(LEADS)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hidden_options_and_usage_counts_are_superadmin_only(self):
        self.assertEqual(
            self.adm.get(field_url("lead_source"), {"include_inactive": "true"}).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        response = self.sa.get(field_url("lead_source"), {"include_inactive": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("usage_count", response.data["options"][0])

    def test_usage_count_reflects_leads(self):
        self.make_lead(self.company_a, self.super_a, "L1", lead_source="Cold Call")
        self.make_lead(self.company_a, self.super_a, "L2", lead_source="Cold Call")
        self.make_lead(self.company_b, self.super_b, "Other tenant", lead_source="Cold Call")

        options = self.options(self.sa, "lead_source", include_inactive="true")
        cold = next(o for o in options if o["value"] == "Cold Call")
        self.assertEqual(cold["usage_count"], 2)


    def test_usage_count_ignores_deleted_and_converted_leads(self):
        self.make_lead(self.company_a, self.super_a, "Visible", lead_source="Cold Call")
        self.make_lead(
            self.company_a, self.super_a, "Deleted", lead_source="Cold Call", is_deleted=True
        )
        self.make_lead(
            self.company_a, self.super_a, "Converted", lead_source="Cold Call", is_converted=True
        )

        options = self.options(self.sa, "lead_source", include_inactive="true")
        cold = next(o for o in options if o["value"] == "Cold Call")
        self.assertEqual(cold["usage_count"], 1)

    def test_option_only_used_by_deleted_leads_can_be_deleted(self):
        hidden = self.make_lead(
            self.company_a, self.super_a, "Gone", lead_source="Cold Call", is_deleted=True
        )
        option_id = self.option_id(self.sa, "lead_source", "Cold Call")

        response = self.sa.delete(delete_url(option_id))

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        hidden.refresh_from_db()
        self.assertEqual(hidden.lead_source, "None")


class CreatingOptionsTests(PicklistTestCase):
    def test_superadmin_can_add_an_option(self):
        created = self.add(self.sa, "lead_source", "LinkedIn")

        self.assertEqual(created["value"], "LinkedIn")
        self.assertTrue(created["is_active"])
        self.assertFalse(created["is_system"])
        self.assertIn("LinkedIn", self.values(self.adm, "lead_source"))
        # Appended at the end.
        self.assertEqual(self.values(self.sa, "lead_source")[-1], "LinkedIn")

    def test_only_company_superadmin_can_add(self):
        response = self.adm.post(create_url("lead_source"), {"value": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_is_rejected_ignoring_case_and_spacing(self):
        self.add(self.sa, "lead_source", "LinkedIn")
        for text in ("linkedin", "  LinkedIn ", "LINKEDIN"):
            response = self.sa.post(create_url("lead_source"), {"value": text}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, text)

    def test_cannot_duplicate_a_built_in_option(self):
        response = self.sa.post(create_url("lead_source"), {"value": "cold call"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_text_is_allowed_in_different_fields(self):
        self.add(self.sa, "lead_source", "Premium")
        self.add(self.sa, "rating", "Premium")

    def test_blank_and_too_long_values_are_rejected(self):
        for bad in ("", "   "):
            response = self.sa.post(create_url("lead_source"), {"value": bad}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, repr(bad))
        response = self.sa.post(create_url("lead_source"), {"value": "x" * 101}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Industry allows 150.
        self.add(self.sa, "industry", "y" * 150)

    def test_inner_whitespace_is_collapsed(self):
        created = self.add(self.sa, "lead_source", "Trade    Fair")
        self.assertEqual(created["value"], "Trade Fair")


class TenantIsolationTests(PicklistTestCase):
    def test_options_are_per_company(self):
        self.add(self.sa, "lead_source", "Only For A")

        self.assertIn("Only For A", self.values(self.sa, "lead_source"))
        self.assertNotIn("Only For A", self.values(self.sb, "lead_source"))

    def test_company_cannot_touch_another_companys_option(self):
        option_id = self.add(self.sa, "lead_source", "Only For A")["id"]

        renamed = self.sb.patch(update_url(option_id), {"value": "Hacked"}, format="json")
        deleted = self.sb.delete(delete_url(option_id))

        self.assertEqual(renamed.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(deleted.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("Only For A", self.values(self.sa, "lead_source"))

    def test_rename_does_not_touch_other_companys_leads(self):
        mine = self.make_lead(self.company_a, self.super_a, "A lead", lead_source="Cold Call")
        theirs = self.make_lead(self.company_b, self.super_b, "B lead", lead_source="Cold Call")

        option_id = self.option_id(self.sa, "lead_source", "Cold Call")
        self.sa.patch(update_url(option_id), {"value": "Outbound Call"}, format="json")

        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertEqual(mine.lead_source, "Outbound Call")
        self.assertEqual(theirs.lead_source, "Cold Call")

    def test_reorder_rejects_another_companys_ids(self):
        self.sb.get(LEADS)
        foreign = [o["id"] for o in self.options(self.sb, "rating", include_inactive="true")]
        response = self.sa.put(
            f"{LEADS}rating/reorder/", {"ordered_ids": foreign}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LeadsUseCompanyOptionsTests(PicklistTestCase):
    def create_lead(self, client=None, **extra):
        return (client or self.sa).post(
            "/api/leads/create/", self.lead_payload(**extra), format="json"
        )

    def lead_row(self, response):
        return DjangoLeadModel.objects.get(pk=response.data["id"])

    def test_a_new_custom_option_can_be_used_on_a_lead(self):
        self.add(self.sa, "lead_source", "LinkedIn")
        self.add(self.sa, "lead_status", "Demo Booked")
        self.add(self.sa, "industry", "Space Tourism")
        self.add(self.sa, "rating", "Platinum")

        response = self.create_lead(
            lead_source="LinkedIn",
            lead_status="Demo Booked",
            industry="Space Tourism",
            rating="Platinum",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        row = self.lead_row(response)
        self.assertEqual(
            (row.lead_source, row.lead_status, row.industry, row.rating),
            ("LinkedIn", "Demo Booked", "Space Tourism", "Platinum"),
        )

    def test_an_option_that_was_never_added_is_rejected(self):
        response = self.create_lead(lead_source="LinkedIn")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("LinkedIn", response.data["detail"])

    def test_options_of_another_company_are_rejected(self):
        self.add(self.sb, "lead_source", "Only For B")
        response = self.create_lead(lead_source="Only For B")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_default_options_still_work_and_blank_becomes_none(self):
        response = self.create_lead(lead_source="Cold Call", lead_status="Contacted")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        row = self.lead_row(response)
        self.assertEqual((row.lead_source, row.lead_status), ("Cold Call", "Contacted"))

        response = self.create_lead()
        row = self.lead_row(response)
        self.assertEqual(
            (row.lead_source, row.lead_status, row.industry, row.rating),
            ("None",) * 4,
        )

    def test_value_is_stored_with_the_options_own_spelling(self):
        response = self.create_lead(lead_source="cold call")
        self.assertEqual(self.lead_row(response).lead_source, "Cold Call")

    def test_update_accepts_a_custom_option_and_rejects_unknown(self):
        lead = self.lead_row(self.create_lead())
        self.add(self.sa, "lead_status", "Demo Booked")
        url = f"/api/leads/{lead.id}/update/"

        ok = self.sa.patch(url, {"lead_status": "Demo Booked"}, format="json")
        self.assertEqual(ok.status_code, status.HTTP_200_OK, ok.content)
        lead.refresh_from_db()
        self.assertEqual(lead.lead_status, "Demo Booked")

        bad = self.sa.patch(url, {"lead_status": "Nonsense"}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        lead.refresh_from_db()
        self.assertEqual(lead.lead_status, "Demo Booked")

    def test_lead_details_and_list_return_the_custom_text(self):
        self.add(self.sa, "lead_source", "LinkedIn")
        lead = self.lead_row(self.create_lead(lead_source="LinkedIn"))

        detail = self.sa.get(f"/api/leads/{lead.id}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK, detail.content)
        self.assertEqual(detail.data["lead_source"], "LinkedIn")

        listing = self.sa.get("/api/leads/")
        self.assertEqual(listing.data["results"][0]["lead_source"], "LinkedIn")

    def test_list_can_be_filtered_by_a_custom_option(self):
        self.add(self.sa, "lead_source", "LinkedIn")
        self.create_lead(name="From LinkedIn", lead_source="LinkedIn")
        self.create_lead(name="From Cold Call", lead_source="Cold Call")

        filters = json.dumps(
            [{"field": "lead_source", "operator": "equals", "value": "LinkedIn"}]
        )
        response = self.sa.get("/api/leads/", {"filters": filters})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual([r["name"] for r in response.data["results"]], ["From LinkedIn"])

    def test_filtering_by_an_unused_value_matches_nothing(self):
        self.create_lead(lead_source="Cold Call")
        filters = json.dumps(
            [{"field": "lead_source", "operator": "equals", "value": "Never Used"}]
        )
        response = self.sa.get("/api/leads/", {"filters": filters})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_converting_a_lead_with_custom_options_works(self):
        self.add(self.sa, "industry", "Space Tourism")
        self.add(self.sa, "rating", "Platinum")
        self.add(self.sa, "lead_source", "LinkedIn")
        lead = self.lead_row(
            self.create_lead(
                company_name="Orbit Ltd",
                industry="Space Tourism",
                rating="Platinum",
                lead_source="LinkedIn",
            )
        )

        response = self.sa.post(
            f"/api/leads/{lead.id}/convert/",
            {"create_account": True, "create_contact": True},
            format="json",
        )

        # Whatever the convert payload requires, it must not fail because
        # the option text is not one of the old fixed enum members.
        self.assertNotEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class RenamingTests(PicklistTestCase):
    def test_rename_updates_every_lead_using_it_even_deleted_ones(self):
        live = self.make_lead(self.company_a, self.super_a, "Live", lead_source="Cold Call")
        gone = self.make_lead(
            self.company_a, self.super_a, "Gone", lead_source="Cold Call", is_deleted=True
        )
        other = self.make_lead(self.company_a, self.super_a, "Other", lead_source="Partner")

        option_id = self.option_id(self.sa, "lead_source", "Cold Call")
        response = self.sa.patch(update_url(option_id), {"value": "Outbound Call"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data["value"], "Outbound Call")
        for lead in (live, gone, other):
            lead.refresh_from_db()
        self.assertEqual(live.lead_source, "Outbound Call")
        self.assertEqual(gone.lead_source, "Outbound Call")
        self.assertEqual(other.lead_source, "Partner")
        self.assertIn("Outbound Call", self.values(self.sa, "lead_source"))
        self.assertNotIn("Cold Call", self.values(self.sa, "lead_source"))

    def test_changing_only_the_case_is_allowed(self):
        option_id = self.option_id(self.sa, "lead_source", "Cold Call")
        response = self.sa.patch(update_url(option_id), {"value": "COLD CALL"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

    def test_rename_to_an_existing_option_is_rejected(self):
        option_id = self.option_id(self.sa, "lead_source", "Cold Call")
        response = self.sa.patch(update_url(option_id), {"value": "partner"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_built_in_none_cannot_be_changed(self):
        none_id = self.option_id(self.sa, "lead_status", "None")
        for body in ({"value": "Nothing"}, {"is_active": False}):
            response = self.sa.patch(update_url(none_id), body, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, body)

    def test_only_superadmin_can_rename(self):
        option_id = self.option_id(self.sa, "lead_source", "Cold Call")
        response = self.adm.patch(update_url(option_id), {"value": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_empty_patch_is_rejected(self):
        option_id = self.option_id(self.sa, "lead_source", "Cold Call")
        response = self.sa.patch(update_url(option_id), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class HidingTests(PicklistTestCase):
    def test_hidden_option_disappears_from_forms_but_not_from_admin_view(self):
        option_id = self.option_id(self.sa, "lead_source", "Cold Call")
        self.sa.patch(update_url(option_id), {"is_active": False}, format="json")

        self.assertNotIn("Cold Call", self.values(self.adm, "lead_source"))
        self.assertIn("Cold Call", self.values(self.sa, "lead_source", include_inactive="true"))

    def test_hidden_option_cannot_be_chosen_for_new_leads(self):
        option_id = self.option_id(self.sa, "lead_source", "Cold Call")
        self.sa.patch(update_url(option_id), {"is_active": False}, format="json")

        response = self.sa.post(
            "/api/leads/create/", self.lead_payload(lead_source="Cold Call"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no longer available", response.data["detail"])

    def test_editing_an_old_lead_still_works_after_its_option_is_hidden(self):
        lead = self.make_lead(self.company_a, self.super_a, "Old", lead_source="Cold Call")
        option_id = self.option_id(self.sa, "lead_source", "Cold Call")
        self.sa.patch(update_url(option_id), {"is_active": False}, format="json")

        # The form re-sends the unchanged hidden value along with the edit.
        response = self.sa.patch(
            f"/api/leads/{lead.id}/update/",
            {"name": "Old renamed", "lead_source": "Cold Call"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        lead.refresh_from_db()
        self.assertEqual((lead.name, lead.lead_source), ("Old renamed", "Cold Call"))

    def test_a_hidden_option_can_be_shown_again(self):
        option_id = self.option_id(self.sa, "lead_source", "Cold Call")
        self.sa.patch(update_url(option_id), {"is_active": False}, format="json")
        self.sa.patch(update_url(option_id), {"is_active": True}, format="json")
        self.assertIn("Cold Call", self.values(self.adm, "lead_source"))


class DeletingTests(PicklistTestCase):
    def test_unused_option_can_be_deleted(self):
        option_id = self.add(self.sa, "lead_source", "LinkedIn")["id"]

        response = self.sa.delete(delete_url(option_id))

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertNotIn("LinkedIn", self.values(self.sa, "lead_source", include_inactive="true"))

    def test_option_in_use_is_blocked_with_a_usage_count(self):
        self.make_lead(self.company_a, self.super_a, "L1", lead_source="Cold Call")
        self.make_lead(self.company_a, self.super_a, "L2", lead_source="Cold Call")
        option_id = self.option_id(self.sa, "lead_source", "Cold Call")

        response = self.sa.delete(delete_url(option_id))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "OPTION_IN_USE")
        self.assertEqual(response.data["usage_count"], 2)
        self.assertIn("Cold Call", self.values(self.sa, "lead_source"))

    def test_option_in_use_can_be_deleted_with_a_replacement(self):
        a = self.make_lead(self.company_a, self.super_a, "L1", lead_source="Cold Call")
        b = self.make_lead(
            self.company_a, self.super_a, "L2", lead_source="Cold Call", is_deleted=True
        )
        option_id = self.option_id(self.sa, "lead_source", "Cold Call")
        replacement_id = self.option_id(self.sa, "lead_source", "Partner")

        response = self.sa.delete(delete_url(option_id), {"replace_with": replacement_id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data["records_updated"], 2)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual((a.lead_source, b.lead_source), ("Partner", "Partner"))
        self.assertNotIn("Cold Call", self.values(self.sa, "lead_source", include_inactive="true"))

    def test_replacement_can_be_given_in_the_query_string(self):
        lead = self.make_lead(self.company_a, self.super_a, "L1", lead_source="Cold Call")
        option_id = self.option_id(self.sa, "lead_source", "Cold Call")
        replacement_id = self.option_id(self.sa, "lead_source", "Partner")

        response = self.sa.delete(f"{delete_url(option_id)}?replace_with={replacement_id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        lead.refresh_from_db()
        self.assertEqual(lead.lead_source, "Partner")

    def test_bad_replacements_are_rejected_and_nothing_changes(self):
        lead = self.make_lead(self.company_a, self.super_a, "L1", lead_source="Cold Call")
        option_id = self.option_id(self.sa, "lead_source", "Cold Call")
        hidden_id = self.option_id(self.sa, "lead_source", "Partner")
        self.sa.patch(update_url(hidden_id), {"is_active": False}, format="json")
        other_field_id = self.option_id(self.sa, "rating", "Active")
        foreign_id = self.add(self.sb, "lead_source", "B only")["id"]

        for replacement in (option_id, hidden_id, other_field_id, foreign_id):
            response = self.sa.delete(delete_url(option_id), {"replace_with": replacement}, format="json")
            self.assertIn(response.status_code, (400, 404), replacement)

        response = self.sa.delete(delete_url(option_id), {"replace_with": "not-a-uuid"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        lead.refresh_from_db()
        self.assertEqual(lead.lead_source, "Cold Call")
        self.assertIn("Cold Call", self.values(self.sa, "lead_source"))

    def test_built_in_none_cannot_be_deleted(self):
        none_id = self.option_id(self.sa, "lead_source", "None")
        response = self.sa.delete(delete_url(none_id))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_superadmin_can_delete(self):
        option_id = self.add(self.sa, "lead_source", "LinkedIn")["id"]
        response = self.adm.delete(delete_url(option_id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ReorderingTests(PicklistTestCase):
    def ids(self, field):
        return [o["id"] for o in self.options(self.sa, field, include_inactive="true")]

    def test_reorder_changes_the_order_forms_see(self):
        ids = self.ids("rating")
        new_order = [ids[0]] + list(reversed(ids[1:]))

        response = self.sa.put(f"{LEADS}rating/reorder/", {"ordered_ids": new_order}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(self.ids("rating"), new_order)
        self.assertEqual([o["id"] for o in self.options(self.adm, "rating")], new_order)

    def test_new_options_go_after_a_reorder(self):
        ids = self.ids("rating")
        self.sa.put(
            f"{LEADS}rating/reorder/", {"ordered_ids": list(reversed(ids))}, format="json"
        )
        self.add(self.sa, "rating", "Platinum")
        self.assertEqual(self.values(self.sa, "rating")[-1], "Platinum")

    def test_incomplete_or_duplicated_lists_are_rejected(self):
        ids = self.ids("rating")
        for bad in (ids[:-1], ids + [ids[0]], []):
            response = self.sa.put(f"{LEADS}rating/reorder/", {"ordered_ids": bad}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, bad)

    def test_only_superadmin_can_reorder(self):
        ids = self.ids("rating")
        response = self.adm.put(f"{LEADS}rating/reorder/", {"ordered_ids": ids}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
