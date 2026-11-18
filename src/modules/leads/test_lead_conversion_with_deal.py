"""Lead conversion that optionally creates a deal in the same transaction."""
import inspect
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.deals.application.interfaces.deal_repository import DealRepository
from src.modules.deals.deal_factories import (
    make_account,
    make_contact,
    make_lead,
)
from src.modules.deals.domain.enums.deal_stage import DealStage
from src.modules.deals.infrastructure.persistence.django_deal_repository import (
    DjangoDealRepository,
)
from src.modules.deals.infrastructure.persistence.models import DjangoDealModel
from src.modules.leads.application.dto.convert_lead import (
    ConvertDealDTO,
    ConvertLeadDTO,
)
from src.modules.leads.application.use_cases import convert_lead as convert_lead_module
from src.modules.leads.application.use_cases.convert_lead import ConvertLeadUseCase
from src.modules.leads.domain.entities.lead import Lead
from src.modules.leads.domain.entities.lead_industry import LeadIndustry
from src.modules.leads.domain.entities.lead_rating import LeadRating
from src.modules.leads.domain.entities.lead_source import LeadSource
from src.modules.leads.domain.entities.lead_status import LeadStatus
from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_convert_lead_use_case,
)
from src.modules.shared.application.tenant_context import TenantContext
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.timeline.infrastructure.persistence.models import (
    TimelineEvent,
    TimelineEventTarget,
)
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.infrastructure.persistence.models import User

MESSAGE = {"message": "Lead converted successfully."}


class ConversionWithDealBase(APITestCase):
    def setUp(self):
        self.company = make_company("Company A", "company-a")
        self.superadmin = make_user(
            self.company, User.Role.SUPERADMIN, "super@a.example.com", name="Super A",
        )
        self.admin = make_user(
            self.company, User.Role.ADMIN, "admin@a.example.com", name="Admin A",
        )
        self.client = authenticated_client(self.superadmin)

        # The lead is owned by the ADMIN; the SUPERADMIN performs the conversion.
        self.lead = make_lead(
            self.company, self.admin, "Ravi",
            company_name="Ravi's shop", email="ravi@example.com",
            lead_source="Referral",
        )

    def convert(self, lead=None, **payload):
        payload.setdefault("account_action", "create_new")
        payload.setdefault("contact_action", "create_new")
        lead = lead or self.lead
        return self.client.post(
            f"/api/leads/{lead.id}/convert/", payload, format="json",
        )

    def counts(self):
        return {
            "accounts": DjangoAccountModel.objects.filter(company=self.company).count(),
            "contacts": DjangoContactModel.objects.filter(company=self.company).count(),
            "deals": DjangoDealModel.objects.filter(company=self.company).count(),
            "events": TimelineEvent.objects.filter(company=self.company).count(),
        }

    def assert_nothing_changed(self, before):
        self.assertEqual(self.counts(), before)
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.is_converted)

    @staticmethod
    def event_targets(event):
        return {
            (kind, str(entity_id))
            for kind, entity_id in TimelineEventTarget.objects.filter(
                event=event
            ).values_list("entity_type", "entity_id")
        }


class ConversionCreatesDealTests(ConversionWithDealBase):
    def test_creates_account_contact_and_deal_together_and_links_them(self):
        response = self.convert(deal={
            "name": "Website for Ravi's shop",
            "amount": "100000.00",
            "expected_close_date": "2026-11-30",
            "stage": "Quotation Sent",
            "probability": 55,
            "description": "Brochure site",
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(set(response.data), {"message", "deal_id"})
        self.assertEqual(response.data["message"], MESSAGE["message"])

        self.lead.refresh_from_db()
        self.assertTrue(self.lead.is_converted)

        account = DjangoAccountModel.objects.get(company=self.company)
        contact = DjangoContactModel.objects.get(company=self.company)
        deal = DjangoDealModel.objects.get(company=self.company)

        self.assertEqual(response.data["deal_id"], str(deal.id))
        self.assertEqual(contact.account_id, account.id)

        self.assertEqual(deal.name, "Website for Ravi's shop")
        self.assertEqual(deal.amount, Decimal("100000.00"))
        self.assertEqual(deal.expected_close_date, date(2026, 11, 30))
        self.assertEqual(deal.stage, "Quotation Sent")
        self.assertEqual(deal.probability, 55)
        self.assertEqual(deal.description, "Brochure site")
        self.assertEqual(deal.account_id, account.id)
        self.assertEqual(deal.contact_id, contact.id)
        self.assertEqual(deal.source_lead_id, self.lead.id)
        self.assertEqual(deal.lead_source, "Referral")
        self.assertEqual(deal.owner_id, self.admin.id)  # the lead's owner
        self.assertEqual(deal.created_by_id, self.superadmin.id)  # who converted
        self.assertEqual(deal.company_id, self.company.id)
        self.assertIsNone(deal.closed_at)
        self.assertFalse(deal.is_deleted)

    def test_deal_defaults_to_new_stage_zero_amount_and_stage_probability(self):
        response = self.convert(deal={"name": "Just a name"})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        deal = DjangoDealModel.objects.get(id=response.data["deal_id"])
        self.assertEqual(deal.stage, "New")
        self.assertEqual(deal.amount, Decimal("0.00"))
        self.assertEqual(deal.probability, 10)
        self.assertIsNone(deal.expected_close_date)
        self.assertIsNone(deal.description)

    def test_created_deal_is_readable_through_the_deals_api(self):
        response = self.convert(deal={"name": "Readable", "amount": "250.50"})

        detail = self.client.get(f"/api/deals/{response.data['deal_id']}/")

        self.assertEqual(detail.status_code, status.HTTP_200_OK, detail.data)
        self.assertEqual(detail.data["source_lead_id"], str(self.lead.id))
        self.assertEqual(detail.data["source_lead_name"], "Ravi")
        self.assertEqual(detail.data["account_name"], "Ravi's shop")
        self.assertEqual(detail.data["contact_name"], "Ravi")
        self.assertEqual(detail.data["owner_name"], "Admin A")

    def test_each_open_stage_is_accepted_with_its_default_probability(self):
        for stage, probability in (("New", 10), ("Quotation Sent", 40), ("Negotiation", 70)):
            with self.subTest(stage=stage):
                lead = make_lead(
                    self.company, self.admin, f"Lead {stage}",
                    company_name=f"Company {stage}",
                )

                response = self.convert(lead=lead, deal={"name": stage, "stage": stage})

                self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
                deal = DjangoDealModel.objects.get(id=response.data["deal_id"])
                self.assertEqual((deal.stage, deal.probability), (stage, probability))

    def test_company_less_lead_creates_the_deal_with_the_contact_only(self):
        lead = make_lead(self.company, self.admin, "Solo Person")

        response = self.convert(lead=lead, account_action="skip", deal={"name": "Solo deal"})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(DjangoAccountModel.objects.filter(company=self.company).count(), 0)
        contact = DjangoContactModel.objects.get(company=self.company)
        deal = DjangoDealModel.objects.get(id=response.data["deal_id"])
        self.assertIsNone(deal.account_id)
        self.assertEqual(deal.contact_id, contact.id)
        self.assertEqual(deal.source_lead_id, lead.id)

    def test_works_when_account_action_is_omitted_for_a_company_less_lead(self):
        lead = make_lead(self.company, self.admin, "Solo Person")

        response = self.client.post(
            f"/api/leads/{lead.id}/convert/",
            {"contact_action": "create_new", "deal": {"name": "Solo deal"}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIsNone(DjangoDealModel.objects.get(id=response.data["deal_id"]).account_id)


class ConversionWithExistingRecordsTests(ConversionWithDealBase):
    def test_use_existing_contact_and_account_links_the_deal_to_them(self):
        account = make_account(self.company, self.admin, "Ravi Traders")
        contact = make_contact(self.company, self.admin, "Ravi (existing)", account=account)
        before = self.counts()

        response = self.convert(
            account_action="use_existing", account_id=str(account.id),
            contact_action="use_existing", contact_id=str(contact.id),
            deal={"name": "Renewal", "amount": "5000"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        deal = DjangoDealModel.objects.get(id=response.data["deal_id"])
        self.assertEqual(deal.contact_id, contact.id)
        self.assertEqual(deal.account_id, account.id)
        self.assertEqual(deal.source_lead_id, self.lead.id)

        after = self.counts()
        self.assertEqual(after["accounts"], before["accounts"])
        self.assertEqual(after["contacts"], before["contacts"])
        self.assertEqual(after["deals"], before["deals"] + 1)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.is_converted)

    def test_use_existing_contact_without_account_gets_the_new_account_and_the_deal_links_both(self):
        contact = make_contact(self.company, self.admin, "Loose Contact")

        response = self.convert(
            contact_action="use_existing", contact_id=str(contact.id),
            deal={"name": "Fresh deal"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        account = DjangoAccountModel.objects.get(company=self.company)
        contact.refresh_from_db()
        deal = DjangoDealModel.objects.get(id=response.data["deal_id"])
        self.assertEqual(contact.account_id, account.id)
        self.assertEqual(deal.contact_id, contact.id)
        self.assertEqual(deal.account_id, account.id)

    def test_use_existing_contact_for_a_company_less_lead_links_the_contact_only(self):
        lead = make_lead(self.company, self.admin, "Solo Person")
        account = make_account(self.company, self.admin, "Contact's Own Co")
        contact = make_contact(self.company, self.admin, "Has account", account=account)

        response = self.convert(
            lead=lead, account_action="skip",
            contact_action="use_existing", contact_id=str(contact.id),
            deal={"name": "Contact-only deal"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        deal = DjangoDealModel.objects.get(id=response.data["deal_id"])
        self.assertEqual(deal.contact_id, contact.id)
        self.assertIsNone(deal.account_id)

    def test_deal_on_a_foreign_companys_contact_is_rejected(self):
        company_b = make_company("Company B", "company-b")
        admin_b = make_user(company_b, User.Role.ADMIN, "admin@b.example.com")
        foreign_contact = make_contact(company_b, admin_b, "Foreign")
        before = self.counts()

        response = self.convert(
            contact_action="use_existing", contact_id=str(foreign_contact.id),
            deal={"name": "Nope"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_nothing_changed(before)
        self.assertEqual(DjangoDealModel.objects.filter(company=company_b).count(), 0)


class ConversionRollbackTests(ConversionWithDealBase):
    def test_negative_amount_is_rejected_and_nothing_is_written(self):
        before = self.counts()

        response = self.convert(deal={"name": "Bad", "amount": "-1"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("deal", response.data)
        self.assert_nothing_changed(before)

    def test_invalid_deal_payloads_are_rejected_and_nothing_is_written(self):
        payloads = {
            "missing name": {"amount": "10"},
            "blank name": {"name": "   "},
            "won stage": {"name": "x", "stage": "Won"},
            "lost stage": {"name": "x", "stage": "Lost"},
            "unknown stage": {"name": "x", "stage": "Nonsense"},
            "probability too high": {"name": "x", "probability": 101},
            "probability negative": {"name": "x", "probability": -1},
            "bad amount": {"name": "x", "amount": "abc"},
            "amount too large": {"name": "x", "amount": "1000000000000.00"},
            "bad date": {"name": "x", "expected_close_date": "2026-13-45"},
        }
        before = self.counts()

        for label, deal in payloads.items():
            with self.subTest(label):
                response = self.convert(deal=deal)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
                self.assert_nothing_changed(before)

    def test_failure_inside_the_transaction_rolls_back_account_and_contact(self):
        # Reaches the deal step through the real wiring, after the Account and
        # the Contact were already saved, and then fails on the amount.
        ctx = TenantContext(
            company_id=self.company.id, user_id=self.superadmin.id,
            role=self.superadmin.role,
        )
        use_case = get_convert_lead_use_case(ctx)
        self.assertIsInstance(use_case.deal_repository, DjangoDealRepository)
        before = self.counts()

        with self.assertRaisesRegex(ValueError, "Amount must be greater than or equal to 0"):
            use_case.execute(
                ConvertLeadDTO(
                    lead_id=self.lead.id,
                    account_action="create_new", account_id=None, account=None,
                    contact_action="create_new", contact_id=None, contact=None,
                    deal=ConvertDealDTO(name="Bad", amount=Decimal("-1")),
                ),
                current_user_id=self.superadmin.id,
            )

        self.assert_nothing_changed(before)

    def test_rejected_deal_after_account_creation_leaves_no_account_or_events(self):
        # Without a deal this exact request succeeds: the existing contact keeps
        # its own account. With a deal it would link a contact to an account it
        # does not belong to, so the deal is rejected and everything rolls back.
        other_account = make_account(self.company, self.admin, "Other Co")
        contact = make_contact(self.company, self.admin, "Existing", account=other_account)
        before = self.counts()

        response = self.convert(
            contact_action="use_existing", contact_id=str(contact.id),
            deal={"name": "Mismatch"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("different account", response.data["detail"])
        self.assert_nothing_changed(before)
        self.assertFalse(
            DjangoAccountModel.objects.filter(account_name="Ravi's shop").exists()
        )
        contact.refresh_from_db()
        self.assertEqual(contact.account_id, other_account.id)

        # The same request without a deal still converts.
        response = self.convert(
            contact_action="use_existing", contact_id=str(contact.id),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data, MESSAGE)


class ConversionWithoutDealTests(ConversionWithDealBase):
    def test_without_a_deal_key_the_behaviour_is_unchanged(self):
        response = self.convert()

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data, MESSAGE)
        self.assertNotIn("deal_id", response.data)

        self.lead.refresh_from_db()
        self.assertTrue(self.lead.is_converted)
        account = DjangoAccountModel.objects.get(company=self.company)
        contact = DjangoContactModel.objects.get(company=self.company)
        self.assertEqual(contact.account_id, account.id)
        self.assertEqual(DjangoDealModel.objects.count(), 0)
        self.assertFalse(
            TimelineEvent.objects.filter(event_type="DEAL_CREATED").exists()
        )

    def test_a_null_deal_is_the_same_as_no_deal(self):
        response = self.convert(deal=None)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data, MESSAGE)
        self.assertEqual(DjangoDealModel.objects.count(), 0)

    def test_existing_failure_modes_still_answer_as_before(self):
        self.convert()

        response = self.convert()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"detail": "Lead is already converted."})


class ConversionDealTimelineTests(ConversionWithDealBase):
    def deal_created_events(self):
        return list(TimelineEvent.objects.filter(
            company=self.company, event_type="DEAL_CREATED",
        ))

    def test_deal_created_is_recorded_with_the_conversion_source(self):
        response = self.convert(deal={"name": "Timeline deal", "amount": "10"})
        deal_id = response.data["deal_id"]
        account = DjangoAccountModel.objects.get(company=self.company)
        contact = DjangoContactModel.objects.get(company=self.company)

        (event,) = self.deal_created_events()

        self.assertEqual(event.actor_id, self.superadmin.id)
        self.assertEqual(event.metadata["source"], "LEAD_CONVERSION")
        self.assertEqual(event.metadata["source_lead_id"], str(self.lead.id))
        self.assertEqual(event.metadata["source_lead_name"], "Ravi")
        self.assertEqual(event.metadata["deal_id"], deal_id)
        self.assertEqual(
            self.event_targets(event),
            {
                ("DEAL", deal_id),
                ("CONTACT", str(contact.id)),
                ("ACCOUNT", str(account.id)),
            },
        )

    def test_event_shows_on_the_contact_account_and_deal_timelines(self):
        response = self.convert(deal={"name": "Timeline deal"})
        deal_id = response.data["deal_id"]
        account = DjangoAccountModel.objects.get(company=self.company)
        contact = DjangoContactModel.objects.get(company=self.company)

        for url in (
            f"/api/timeline/contacts/{contact.id}/",
            f"/api/timeline/accounts/{account.id}/",
            f"/api/timeline/deals/{deal_id}/",
        ):
            with self.subTest(url=url):
                timeline = self.client.get(url)

                self.assertEqual(timeline.status_code, status.HTTP_200_OK)
                self.assertIn(
                    "DEAL_CREATED", [event["event_type"] for event in timeline.data],
                )

    def test_company_less_lead_event_targets_deal_and_contact_only(self):
        lead = make_lead(self.company, self.admin, "Solo Person")

        response = self.convert(lead=lead, account_action="skip", deal={"name": "Solo"})
        contact = DjangoContactModel.objects.get(company=self.company)

        (event,) = self.deal_created_events()
        self.assertEqual(
            self.event_targets(event),
            {("DEAL", response.data["deal_id"]), ("CONTACT", str(contact.id))},
        )

    def test_existing_contact_gets_the_event_on_its_timeline(self):
        account = make_account(self.company, self.admin, "Ravi Traders")
        contact = make_contact(self.company, self.admin, "Ravi (existing)", account=account)

        self.convert(
            account_action="use_existing", account_id=str(account.id),
            contact_action="use_existing", contact_id=str(contact.id),
            deal={"name": "Renewal"},
        )

        timeline = self.client.get(f"/api/timeline/contacts/{contact.id}/")
        self.assertIn("DEAL_CREATED", [event["event_type"] for event in timeline.data])

    def test_conversion_still_records_its_other_events(self):
        self.convert(deal={"name": "Timeline deal"})

        types = set(
            TimelineEvent.objects.filter(company=self.company).values_list(
                "event_type", flat=True,
            )
        )
        self.assertTrue(
            {"ACCOUNT_CREATED", "CONTACT_CREATED", "DEAL_CREATED", "LEAD_CONVERTED"} <= types,
            types,
        )


class ConvertLeadUseCaseWithDealUnitTests(SimpleTestCase):
    """The use case only talks to the DealRepository interface."""

    def _lead(self, company_name="Ravi's shop"):
        return Lead.create(
            name="Ravi", title=None, company_name=company_name,
            email="ravi@example.com", mobile_number="9999999999", phone=None,
            lead_source=LeadSource.NONE, lead_status=LeadStatus.NONE,
            industry=LeadIndustry.NONE, rating=LeadRating.NONE, website=None,
            number_of_employees=None, annual_revenue=None, owner_id=uuid4(),
            address=None, city=None, state=None, country=None, postal_code=None,
            description=None,
        )

    def _build(self, lead, with_deal_repository=True):
        lead_repository = Mock()
        lead_repository.get_by_id.return_value = lead
        lead_repository.save.side_effect = lambda value: value
        user_repository = Mock()
        user_repository.get_by_id.return_value = SimpleNamespace(
            is_active=True, role=UserRole.ADMIN,
        )
        account_repository = Mock()
        account_repository.save.side_effect = lambda value: value
        contact_repository = Mock()
        contact_repository.save.side_effect = lambda value: value
        transaction_manager = Mock()
        transaction_manager.execute.side_effect = lambda operation: operation()
        timeline_recorder = Mock()
        deal_repository = Mock(spec=DealRepository)
        deal_repository.save.side_effect = lambda value: value

        kwargs = {"deal_repository": deal_repository} if with_deal_repository else {}
        use_case = ConvertLeadUseCase(
            lead_repository, account_repository, contact_repository,
            user_repository, transaction_manager, timeline_recorder, **kwargs,
        )
        return use_case, SimpleNamespace(
            lead=lead_repository, account=account_repository,
            contact=contact_repository, deal=deal_repository,
            timeline=timeline_recorder,
        )

    @staticmethod
    def _dto(lead, deal):
        return ConvertLeadDTO(
            lead.id, "create_new", None, None, "create_new", None, None, deal=deal,
        )

    def test_deal_is_saved_after_account_and_contact_and_before_the_lead_is_converted(self):
        lead = self._lead()
        use_case, mocks = self._build(lead)
        seen = []

        def save_deal(deal):
            seen.append({
                "lead_converted": lead.is_converted,
                "account_saved": mocks.account.save.called,
                "contact_saved": mocks.contact.save.called,
            })
            return deal

        mocks.deal.save.side_effect = save_deal

        result = use_case.execute(
            self._dto(lead, ConvertDealDTO(name="Deal", amount=Decimal("10"))),
            uuid4(),
        )

        self.assertEqual(
            seen, [{"lead_converted": False, "account_saved": True, "contact_saved": True}],
        )
        self.assertTrue(lead.is_converted)
        deal = mocks.deal.save.call_args.args[0]
        self.assertEqual(result.deal_id, deal.id)
        self.assertEqual(deal.source_lead_id, lead.id)
        self.assertEqual(deal.owner_id, lead.owner_id)
        self.assertEqual(deal.account_id, mocks.account.save.call_args.args[0].id)
        self.assertEqual(deal.contact_id, mocks.contact.save.call_args.args[0].id)
        self.assertEqual(deal.stage, DealStage.NEW)

    def test_invalid_deal_stops_the_conversion_before_the_lead_is_marked(self):
        lead = self._lead()
        use_case, mocks = self._build(lead)

        with self.assertRaises(ValueError):
            use_case.execute(
                self._dto(lead, ConvertDealDTO(name="Bad", amount=Decimal("-5"))),
                uuid4(),
            )

        mocks.deal.save.assert_not_called()
        mocks.lead.save.assert_not_called()
        self.assertFalse(lead.is_converted)

    def test_closed_stage_is_rejected(self):
        for stage in (DealStage.WON, DealStage.LOST):
            with self.subTest(stage=stage):
                lead = self._lead()
                use_case, mocks = self._build(lead)

                with self.assertRaisesRegex(ValueError, "open stage"):
                    use_case.execute(
                        self._dto(lead, ConvertDealDTO(name="x", stage=stage)),
                        uuid4(),
                    )

                mocks.deal.save.assert_not_called()
                self.assertFalse(lead.is_converted)

    def test_without_a_deal_the_repository_is_never_touched(self):
        lead = self._lead()
        use_case, mocks = self._build(lead)

        result = use_case.execute(self._dto(lead, None), uuid4())

        mocks.deal.save.assert_not_called()
        self.assertIsNone(result.deal_id)
        self.assertTrue(lead.is_converted)

    def test_without_a_deal_the_repository_is_optional(self):
        lead = self._lead()
        use_case, _ = self._build(lead, with_deal_repository=False)

        result = use_case.execute(self._dto(lead, None), uuid4())

        self.assertIsNone(result.deal_id)
        self.assertTrue(lead.is_converted)

    def test_a_deal_without_a_configured_repository_is_a_programming_error(self):
        lead = self._lead()
        use_case, _ = self._build(lead, with_deal_repository=False)

        with self.assertRaises(RuntimeError):
            use_case.execute(self._dto(lead, ConvertDealDTO(name="x")), uuid4())

        self.assertFalse(lead.is_converted)

    def test_leads_use_case_does_not_import_the_django_deal_model(self):
        source = inspect.getsource(convert_lead_module)

        self.assertNotIn("DjangoDealModel", source)
        self.assertNotIn("django_deal_model", source)
        self.assertNotIn("deals.infrastructure", source)
        self.assertIn("deals.application.interfaces.deal_repository", source)
