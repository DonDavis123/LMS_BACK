from datetime import datetime, timezone
from uuid import uuid4

from django.test import TestCase

from src.modules.leads.application.dto.convert_lead import ConvertLeadDTO
from src.modules.leads.application.use_cases.convert_lead import ConvertLeadUseCase
from src.modules.leads.application.use_cases.update_lead import UpdateLeadUseCase
from src.modules.leads.application.dto.update_lead import UpdateLeadDTO
from src.modules.leads.domain.entities.lead import Lead
from src.modules.leads.domain.entities.lead_industry import LeadIndustry
from src.modules.leads.domain.entities.lead_rating import LeadRating
from src.modules.leads.domain.entities.lead_source import LeadSource
from src.modules.leads.domain.entities.lead_status import LeadStatus
from src.modules.accounts.domain.entities.account import Account
from src.modules.contacts.domain.entities.contact import Contact
from src.modules.timeline.application.services.change_tracker import (
    build_field_changes,
    format_field_changes,
    resolve_relationship_changes,
)
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User


class RecordingTimelineRecorder:
    def __init__(self):
        self.events = []

    def record(self, **kwargs):
        self.events.append(kwargs)


class ImmediateTransactionManager:
    def execute(self, operation):
        return operation()


class InMemoryLeadRepository:
    def __init__(self, lead):
        self.lead = lead

    def get_by_id(self, lead_id):
        return self.lead if self.lead.id == lead_id else None

    def save(self, lead):
        self.lead = lead
        return lead


class InMemoryAccountRepository:
    def __init__(self):
        self.accounts = {}

    def save(self, account):
        self.accounts[account.id] = account
        return account

    def get_by_id(self, account_id):
        return self.accounts.get(account_id)


class InMemoryContactRepository:
    def __init__(self):
        self.contacts = {}

    def save(self, contact):
        self.contacts[contact.id] = contact
        return contact

    def get_by_id(self, contact_id):
        return self.contacts.get(contact_id)


class InMemoryUserRepository:
    def __init__(self, user):
        self.user = user

    def get_by_id(self, user_id):
        return self.user if self.user.id == user_id else None


class TimelineEnhancementTests(TestCase):
    def setUp(self):
        self.user_id = uuid4()
        self.user = User(
            id=self.user_id,
            name="Don Davis",
            email="don@example.com",
            role=UserRole.ADMIN,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.lead = Lead.create(
            name="AAthish",
            title="Manager",
            company_name="ABC Ltd",
            email="aathish@example.com",
            mobile_number="9999999999",
            phone=None,
            lead_source=LeadSource.NONE,
            lead_status=LeadStatus.ATTEMPTED_TO_CONTACT,
            industry=LeadIndustry.NONE,
            rating=LeadRating.NONE,
            website=None,
            number_of_employees=10,
            annual_revenue=100000,
            owner_id=self.user_id,
            address=None,
            city="Kochi",
            state="Kerala",
            country="India",
            postal_code="682001",
            description=None,
        )

    def test_lead_update_message_contains_all_changed_fields(self):
        lead_repository = InMemoryLeadRepository(self.lead)
        recorder = RecordingTimelineRecorder()

        use_case = UpdateLeadUseCase(
            lead_repository=lead_repository,
            user_repository=InMemoryUserRepository(self.user),
            timeline_recorder=recorder,
            transaction_manager=ImmediateTransactionManager(),
        )

        use_case.execute(
            UpdateLeadDTO(
                lead_id=self.lead.id,
                name="Rahul",
                company_name="XYZ Ltd",
                lead_status=LeadStatus.CONTACTED,
            ),
            current_user_id=self.user_id,
        )

        self.assertEqual(len(recorder.events), 1)
        event = recorder.events[0]

        self.assertEqual(event["event_type"], "LEAD_UPDATED")
        self.assertEqual(
            event["metadata"]["changes"]["name"],
            {"old_value": "AAthish", "new_value": "Rahul"},
        )
        self.assertEqual(
            event["metadata"]["changes"]["company_name"],
            {"old_value": "ABC Ltd", "new_value": "XYZ Ltd"},
        )
        self.assertEqual(
            event["metadata"]["changes"]["lead_status"],
            {
                "old_value": "Attempted to Contact",
                "new_value": "Contacted",
            },
        )
        self.assertIn("Name: AAthish → Rahul", event["message"])
        self.assertIn("Company Name: ABC Ltd → XYZ Ltd", event["message"])
        self.assertIn(
            "Lead Status: Attempted to Contact → Contacted",
            event["message"],
        )

    def test_lead_owner_change_uses_user_name_not_uuid(self):
        new_owner = User(
            id=uuid4(),
            name="Jane Owner",
            email="jane@example.com",
            role=UserRole.ADMIN,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        class MultiUserRepository:
            def __init__(self, users):
                self.users = {user.id: user for user in users}

            def get_by_id(self, user_id):
                return self.users.get(user_id)

        recorder = RecordingTimelineRecorder()
        use_case = UpdateLeadUseCase(
            lead_repository=InMemoryLeadRepository(self.lead),
            user_repository=MultiUserRepository([self.user, new_owner]),
            timeline_recorder=recorder,
            transaction_manager=ImmediateTransactionManager(),
        )

        use_case.execute(
            UpdateLeadDTO(lead_id=self.lead.id, owner_id=new_owner.id),
            current_user_id=self.user_id,
        )

        event = recorder.events[0]
        self.assertEqual(
            event["metadata"]["changes"]["owner_id"],
            {"old_value": self.user.name, "new_value": new_owner.name},
        )
        self.assertIn("Owner: Don Davis → Jane Owner", event["message"])
        self.assertNotIn(str(self.user_id), event["message"])
        self.assertNotIn(str(new_owner.id), event["message"])

    def test_relationship_change_resolver_preserves_null_and_resolves_names(self):
        old_id = uuid4()
        new_id = uuid4()
        changes = {
            "owner_id": {
                "old_value": str(old_id),
                "new_value": str(new_id),
            }
        }

        resolved = resolve_relationship_changes(
            changes,
            {"owner_id": lambda value: "Old Owner" if value == old_id else "New Owner"},
        )

        self.assertEqual(
            resolved["owner_id"],
            {"old_value": "Old Owner", "new_value": "New Owner"},
        )

        null_changes = {
            "owner_id": {"old_value": None, "new_value": str(new_id)}
        }
        resolved_null = resolve_relationship_changes(
            null_changes,
            {"owner_id": lambda value: "New Owner"},
        )
        self.assertEqual(
            resolved_null["owner_id"],
            {"old_value": None, "new_value": "New Owner"},
        )

    def test_lead_noop_update_does_not_create_timeline_event(self):
        lead_repository = InMemoryLeadRepository(self.lead)
        recorder = RecordingTimelineRecorder()

        use_case = UpdateLeadUseCase(
            lead_repository=lead_repository,
            user_repository=InMemoryUserRepository(self.user),
            timeline_recorder=recorder,
            transaction_manager=ImmediateTransactionManager(),
        )

        use_case.execute(
            UpdateLeadDTO(
                lead_id=self.lead.id,
                name="AAthish",
            ),
            current_user_id=self.user_id,
        )

        self.assertEqual(recorder.events, [])

    def test_conversion_creates_account_and_contact_timeline_links(self):
        lead_repository = InMemoryLeadRepository(self.lead)
        account_repository = InMemoryAccountRepository()
        contact_repository = InMemoryContactRepository()
        recorder = RecordingTimelineRecorder()

        use_case = ConvertLeadUseCase(
            lead_repository=lead_repository,
            account_repository=account_repository,
            contact_repository=contact_repository,
            user_repository=InMemoryUserRepository(self.user),
            transaction_manager=ImmediateTransactionManager(),
            timeline_recorder=recorder,
        )

        use_case.execute(
            ConvertLeadDTO(
                lead_id=self.lead.id,
                account_action="create_new",
                account_id=None,
                account=None,
                contact_action="create_new",
                contact_id=None,
                contact=None,
            ),
            current_user_id=self.user_id,
        )

        account_events = [
            event
            for event in recorder.events
            if event["event_type"] == "ACCOUNT_CREATED"
        ]
        contact_events = [
            event
            for event in recorder.events
            if event["event_type"] == "CONTACT_CREATED"
        ]
        conversion_events = [
            event
            for event in recorder.events
            if event["event_type"] == "LEAD_CONVERTED"
        ]

        self.assertEqual(len(account_events), 1)
        self.assertEqual(len(contact_events), 1)
        self.assertEqual(len(conversion_events), 1)

        account_event = account_events[0]
        self.assertEqual(
            account_event["message"],
            "Account created by converting the Lead AAthish",
        )
        self.assertEqual(account_event["metadata"]["source"], "LEAD_CONVERSION")
        self.assertEqual(
            account_event["metadata"]["source_lead_id"],
            str(self.lead.id),
        )
        self.assertEqual(
            account_event["metadata"]["source_lead_name"],
            "AAthish",
        )

        contact_event = contact_events[0]
        self.assertEqual(
            contact_event["message"],
            "Contact created by converting the Lead AAthish",
        )
        self.assertEqual(contact_event["metadata"]["source"], "LEAD_CONVERSION")
        self.assertEqual(
            contact_event["metadata"]["source_lead_id"],
            str(self.lead.id),
        )
        self.assertEqual(
            contact_event["metadata"]["source_lead_name"],
            "AAthish",
        )

        conversion_event = conversion_events[0]
        self.assertEqual(
            conversion_event["metadata"]["source_lead_id"],
            str(self.lead.id),
        )


    def test_conversion_using_existing_records_does_not_emit_created_events(self):
        account_repository = InMemoryAccountRepository()
        contact_repository = InMemoryContactRepository()
        existing_account = Account.create(
            account_owner_id=self.user_id,
            account_name="Existing Account",
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
            created_by_id=self.user_id,
        )
        existing_contact = Contact.create(
            account_id=existing_account.id,
            contact_owner_id=self.user_id,
            name="Existing Contact",
            email="contact@example.com",
            secondary_email=None,
            phone=None,
            other_phone=None,
            mobile=None,
            home_phone=None,
            assistant_phone=None,
            title=None,
            department=None,
            lead_source=None,
            vendor_name=None,
            date_of_birth=None,
            assistant=None,
            email_opt_out=False,
            reporting_to_id=None,
            mailing_address=None,
            mailing_city=None,
            mailing_state=None,
            mailing_country=None,
            mailing_postal_code=None,
            other_address=None,
            description=None,
            created_by_id=self.user_id,
        )
        account_repository.save(existing_account)
        contact_repository.save(existing_contact)
        recorder = RecordingTimelineRecorder()

        use_case = ConvertLeadUseCase(
            lead_repository=InMemoryLeadRepository(self.lead),
            account_repository=account_repository,
            contact_repository=contact_repository,
            user_repository=InMemoryUserRepository(self.user),
            transaction_manager=ImmediateTransactionManager(),
            timeline_recorder=recorder,
        )

        use_case.execute(
            ConvertLeadDTO(
                lead_id=self.lead.id,
                account_action="use_existing",
                account_id=existing_account.id,
                account=None,
                contact_action="use_existing",
                contact_id=existing_contact.id,
                contact=None,
            ),
            current_user_id=self.user_id,
        )

        created_events = [
            event for event in recorder.events
            if event["event_type"] in {"ACCOUNT_CREATED", "CONTACT_CREATED"}
        ]
        self.assertEqual(created_events, [])

        conversion_event = next(
            event for event in recorder.events
            if event["event_type"] == "LEAD_CONVERTED"
        )
        self.assertEqual(
            conversion_event["metadata"]["source_lead_id"],
            str(self.lead.id),
        )

    def test_change_tracker_serializes_supported_values(self):
        value_id = uuid4()
        old_values = {
            "status": LeadStatus.ATTEMPTED_TO_CONTACT,
            "owner_id": value_id,
            "when": datetime(2026, 9, 23, 10, 30, tzinfo=timezone.utc),
            "count": 1,
            "enabled": False,
            "description": None,
        }
        new_values = {
            "status": LeadStatus.CONTACTED,
            "owner_id": uuid4(),
            "when": datetime(2026, 9, 23, 11, 30, tzinfo=timezone.utc),
            "count": 2,
            "enabled": True,
            "description": "Updated",
        }

        changes = build_field_changes(old_values, new_values)

        self.assertEqual(
            changes["status"],
            {
                "old_value": "Attempted to Contact",
                "new_value": "Contacted",
            },
        )
        self.assertEqual(changes["owner_id"]["old_value"], str(value_id))
        self.assertIsInstance(changes["when"]["old_value"], str)
        self.assertEqual(changes["count"], {"old_value": 1, "new_value": 2})
        self.assertEqual(
            changes["enabled"],
            {"old_value": False, "new_value": True},
        )
        self.assertEqual(
            changes["description"],
            {"old_value": None, "new_value": "Updated"},
        )

        summary = format_field_changes(
            {"name": {"old_value": "Old", "new_value": "New"}},
            {"name": "Name"},
        )
        self.assertEqual(summary, "Name: Old → New")
