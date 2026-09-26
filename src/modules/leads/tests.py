from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from django.test import SimpleTestCase

from src.modules.leads.application.dto.convert_lead import ConvertLeadDTO
from src.modules.leads.application.use_cases.convert_lead import ConvertLeadUseCase
from src.modules.leads.application.use_cases.coversion_check import ConversionCheckUseCase
from src.modules.leads.domain.entities.lead import Lead
from src.modules.leads.domain.entities.lead_industry import LeadIndustry
from src.modules.leads.domain.entities.lead_rating import LeadRating
from src.modules.leads.domain.entities.lead_source import LeadSource
from src.modules.leads.domain.entities.lead_status import LeadStatus
from src.modules.users.domain.entities.role import UserRole


class LeadCompanyOptionalTests(SimpleTestCase):

    def _lead(self, company_name=None):
        return Lead.create(
            name="John Doe", title=None, company_name=company_name,
            email="john@example.com", mobile_number="9999999999", phone=None,
            lead_source=LeadSource.NONE, lead_status=LeadStatus.NONE,
            industry=LeadIndustry.NONE, rating=LeadRating.NONE, website=None,
            number_of_employees=None, annual_revenue=None, owner_id=uuid4(),
            address=None, city=None, state=None, country=None, postal_code=None,
            description=None,
        )

    def _use_case(self, lead):
        lead_repository = Mock()
        lead_repository.get_by_id.return_value = lead
        lead_repository.save.side_effect = lambda value: value
        user_repository = Mock()
        user_repository.get_by_id.return_value = SimpleNamespace(
            is_active=True, role=UserRole.ADMIN
        )
        account_repository = Mock()
        contact_repository = Mock()
        timeline_recorder = Mock()
        transaction_manager = Mock()
        transaction_manager.execute.side_effect = lambda operation: operation()
        use_case = ConvertLeadUseCase(
            lead_repository, account_repository, contact_repository,
            user_repository, transaction_manager, timeline_recorder,
        )
        return use_case, lead_repository, account_repository, contact_repository

    def test_companyless_lead_converts_to_contact_without_account(self):
        lead = self._lead(None)
        use_case, lead_repository, account_repository, contact_repository = self._use_case(lead)
        contact_repository.save.side_effect = lambda value: value
        use_case.execute(
            ConvertLeadDTO(lead.id, None, None, None, "create_new", None, None),
            uuid4(),
        )
        account_repository.save.assert_not_called()
        self.assertIsNone(contact_repository.save.call_args.args[0].account_id)
        self.assertTrue(lead.is_converted)
        lead_repository.save.assert_called_once()

    def test_blank_and_whitespace_company_skip_account(self):
        for company_name in ("", "   "):
            with self.subTest(company_name=repr(company_name)):
                lead = self._lead(company_name)
                use_case, _, account_repository, contact_repository = self._use_case(lead)
                contact_repository.save.side_effect = lambda value: value
                use_case.execute(
                    ConvertLeadDTO(lead.id, None, None, None, "create_new", None, None),
                    uuid4(),
                )
                account_repository.save.assert_not_called()
                self.assertIsNone(contact_repository.save.call_args.args[0].account_id)

    def test_conversion_check_does_not_search_accounts_without_company(self):
        lead = self._lead(None)
        lead_repository = Mock()
        lead_repository.get_by_id.return_value = lead
        account_repository = Mock()
        contact_repository = Mock()
        contact_repository.find_conversion_matches.return_value = []
        use_case = ConversionCheckUseCase(lead_repository, account_repository, contact_repository)
        result = use_case.execute(lead.id)
        account_repository.find_conversion_matches.assert_not_called()
        self.assertEqual(result.account_matches, [])

    def test_companyless_lead_can_add_company_during_conversion(self):
        lead = self._lead(None)
        use_case, lead_repository, account_repository, contact_repository = self._use_case(lead)

        account = SimpleNamespace(id=uuid4(), account_name="ABC Technologies", is_deleted=False)
        account_repository.save.side_effect = lambda value: account
        contact_repository.save.side_effect = lambda value: value

        from src.modules.leads.application.dto.convert_lead import ConvertAccountDTO

        account_dto = ConvertAccountDTO(
            account_name="ABC Technologies",
            account_site=None,
            account_number=None,
            account_type=None,
            industry=None,
            annual_revenue=None,
            rating=None,
            phone=None,
            website=None,
            ticker_symbol=None,
            ownership=None,
            employees=None,
            sic_code=None,
            billing_address=None,
            billing_city=None,
            billing_state=None,
            billing_country=None,
            billing_postal_code=None,
            description=None,
        )

        use_case.execute(
            ConvertLeadDTO(
                lead.id,
                "create_new",
                None,
                account_dto,
                "create_new",
                None,
                None,
            ),
            uuid4(),
        )

        account_repository.save.assert_called_once()
        self.assertEqual(
            account_repository.save.call_args.args[0].account_name,
            "ABC Technologies",
        )
        self.assertEqual(
            contact_repository.save.call_args.args[0].account_id,
            account.id,
        )
        self.assertTrue(lead.is_converted)
        lead_repository.save.assert_called_once()

    def test_companyless_lead_cannot_create_account_without_company_name(self):
        lead = self._lead(None)
        use_case, _, account_repository, _ = self._use_case(lead)
        contact_repository = use_case.contact_repository
        contact_repository.save.side_effect = lambda value: value

        with self.assertRaisesRegex(ValueError, r"account\.account_name is required"):
            use_case.execute(
                ConvertLeadDTO(
                    lead.id,
                    "create_new",
                    None,
                    None,
                    "create_new",
                    None,
                    None,
                ),
                uuid4(),
            )

        account_repository.save.assert_not_called()
        self.assertFalse(lead.is_converted)

    def test_companyless_lead_can_use_existing_account(self):
        lead = self._lead(None)
        use_case, _, account_repository, contact_repository = self._use_case(lead)

        account = SimpleNamespace(id=uuid4(), is_deleted=False, account_name="Existing Co")
        account_repository.get_by_id.return_value = account
        contact_repository.save.side_effect = lambda value: value

        use_case.execute(
            ConvertLeadDTO(
                lead.id,
                "use_existing",
                account.id,
                None,
                "create_new",
                None,
                None,
            ),
            uuid4(),
        )

        account_repository.save.assert_not_called()
        self.assertEqual(
            contact_repository.save.call_args.args[0].account_id,
            account.id,
        )
        self.assertTrue(lead.is_converted)

    def test_companyless_lead_can_use_existing_contact_without_account(self):
        lead = self._lead(None)
        use_case, _, account_repository, contact_repository = self._use_case(lead)

        contact = SimpleNamespace(
            id=uuid4(),
            account_id=None,
            is_deleted=False,
        )
        contact_repository.get_by_id.return_value = contact

        use_case.execute(
            ConvertLeadDTO(
                lead.id,
                None,
                None,
                None,
                "use_existing",
                contact.id,
                None,
            ),
            uuid4(),
        )

        account_repository.save.assert_not_called()
        contact_repository.save.assert_not_called()
        self.assertIsNone(contact.account_id)
        self.assertTrue(lead.is_converted)

    def test_company_lead_cannot_skip_account(self):
        lead = self._lead("Existing Company")
        use_case, _, account_repository, contact_repository = self._use_case(lead)
        contact_repository.save.side_effect = lambda value: value

        with self.assertRaisesRegex(ValueError, "Create or select an Account"):
            use_case.execute(
                ConvertLeadDTO(
                    lead.id,
                    None,
                    None,
                    None,
                    "create_new",
                    None,
                    None,
                ),
                uuid4(),
            )

        account_repository.save.assert_not_called()
        contact_repository.save.assert_not_called()
        self.assertFalse(lead.is_converted)
