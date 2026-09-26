from uuid import UUID

from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.accounts.domain.entities.account import Account

from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.contacts.domain.entities.contact import Contact

from src.modules.leads.application.dto.convert_lead import (
    ConvertLeadDTO,
)
from src.modules.leads.application.interfaces.lead_repository import (
    LeadRepository,
)

from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)

from src.modules.users.application.interfaces.user_repository import (
    UserRepository,
)
from src.modules.users.domain.entities.role import UserRole
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder


class ConvertLeadUseCase:

    def __init__(
        self,
        lead_repository: LeadRepository,
        account_repository: AccountRepository,
        contact_repository: ContactRepository,
        user_repository: UserRepository,
        transaction_manager: TransactionManager,
        timeline_recorder: TimelineRecorder,
    ):
        self.lead_repository = lead_repository
        self.account_repository = account_repository
        self.contact_repository = contact_repository
        self.user_repository = user_repository
        self.transaction_manager = transaction_manager
        self.timeline_recorder = timeline_recorder

    def execute(
        self,
        data: ConvertLeadDTO,
        current_user_id: UUID,
    ) -> None:

        # --------------------------------------------------
        # 1. Get and validate Lead
        # --------------------------------------------------

        lead = self.lead_repository.get_by_id(
            data.lead_id,
        )

        if lead is None:
            raise ValueError(
                "Lead not found."
            )

        if lead.is_deleted:
            raise ValueError(
                "Deleted lead cannot be converted."
            )

        if lead.is_converted:
            raise ValueError(
                "Lead is already converted."
            )

        # --------------------------------------------------
        # 2. Validate Lead owner
        # --------------------------------------------------

        owner = self.user_repository.get_by_id(
            lead.owner_id,
        )

        if owner is None:
            raise ValueError(
                "Lead owner does not exist."
            )

        if not owner.is_active:
            raise ValueError(
                "Lead owner is inactive."
            )

        if owner.role not in {
            UserRole.ADMIN,
            UserRole.SUPERADMIN,
        }:
            raise ValueError(
                "Lead owner must be an ADMIN or SUPERADMIN."
            )

        # --------------------------------------------------
        # 3. Execute conversion atomically
        # --------------------------------------------------

        def conversion():

            # ----------------------------------------------
            # Account
            # ----------------------------------------------

            # A lead without a company may be converted as a
            # Contact only. In that case no Account is created
            # or selected.
            account = None

            if data.account_action in {None, "skip"}:

                if self._has_company_name(lead.company_name):
                    raise ValueError(
                        "A company is required for normal lead conversion. "
                        "Create or select an Account."
                    )

            elif data.account_action == "create_new":

                account = self._create_account(
                    lead=lead,
                    data=data,
                    current_user_id=current_user_id,
                )

            elif data.account_action == "use_existing":

                account = self._get_existing_account(
                    data.account_id,
                )

            else:
                raise ValueError(
                    "Invalid account_action."
                )

            # ----------------------------------------------
            # Contact
            # ----------------------------------------------

            if data.contact_action == "create_new":

                self._create_contact(
                    lead=lead,
                    account_id=account.id if account else None,
                    data=data,
                    current_user_id=current_user_id,
                )

            elif data.contact_action == "use_existing":

                contact = self._get_existing_contact(
                    data.contact_id,
                )

                self._use_existing_contact(
                    contact=contact,
                    account=account,
                )

            else:
                raise ValueError(
                    "Invalid contact_action."
                )

            # ----------------------------------------------
            # Mark Lead as converted
            # ----------------------------------------------

            lead.convert()

            self.lead_repository.save(
                lead,
            )
            targets = [("LEAD", lead.id)]
            if data.contact_action == "use_existing" and data.contact_id: targets.append(("CONTACT", data.contact_id))
            if data.account_action == "use_existing" and data.account_id: targets.append(("ACCOUNT", data.account_id))
            self.timeline_recorder.record(
                event_type="LEAD_CONVERTED",
                actor_id=current_user_id,
                message=f"Lead {lead.name} was converted.",
                metadata={
                    "lead_id": str(lead.id),
                    "source": "LEAD_CONVERSION",
                    "source_lead_id": str(lead.id),
                    "source_lead_name": lead.name,
                },
                targets=targets,
            )

        self.transaction_manager.execute(
            conversion,
        )

    # ======================================================
    # ACCOUNT
    # ======================================================

    def _create_account(
        self,
        lead,
        data: ConvertLeadDTO,
        current_user_id: UUID,
    ) -> Account:

        account_data = data.account

        # When account data is not supplied by the frontend,
        # create the Account from the Lead automatically. This is
        # valid only when the Lead already has a company name.
        if account_data is None:

            if not self._has_company_name(lead.company_name):
                raise ValueError(
                    "account.account_name is required when adding a company "
                    "during conversion."
                )

            account = Account.create(
                account_owner_id=lead.owner_id,
                account_name=lead.company_name,
                account_site=None,
                account_number=None,
                account_type=None,
                industry=lead.industry.value,
                annual_revenue=lead.annual_revenue,
                rating=lead.rating.value,
                phone=lead.phone,
                website=lead.website,
                ticker_symbol=None,
                ownership="None",
                employees=lead.number_of_employees,
                sic_code=None,
                billing_address=lead.address,
                billing_city=lead.city,
                billing_state=lead.state,
                billing_country=lead.country,
                billing_postal_code=lead.postal_code,
                description=lead.description,
                created_by_id=current_user_id,
            )

        else:

            account = Account.create(
                account_owner_id=lead.owner_id,
                account_name=account_data.account_name,
                account_site=account_data.account_site,
                account_number=account_data.account_number,
                account_type=account_data.account_type,
                industry=account_data.industry,
                annual_revenue=account_data.annual_revenue,
                rating=account_data.rating,
                phone=account_data.phone,
                website=account_data.website,
                ticker_symbol=account_data.ticker_symbol,
                ownership=account_data.ownership,
                employees=account_data.employees,
                sic_code=account_data.sic_code,
                billing_address=account_data.billing_address,
                billing_city=account_data.billing_city,
                billing_state=account_data.billing_state,
                billing_country=account_data.billing_country,
                billing_postal_code=account_data.billing_postal_code,
                description=account_data.description,
                created_by_id=current_user_id,
            )

        saved = self.account_repository.save(account)

        self.timeline_recorder.record(
            event_type="ACCOUNT_CREATED",
            actor_id=current_user_id,
            message=(
                f"Account created by converting the Lead {lead.name}"
            ),
            metadata={
                "account_id": str(saved.id),
                "account_name": saved.account_name,
                "source": "LEAD_CONVERSION",
                "source_lead_id": str(lead.id),
                "source_lead_name": lead.name,
            },
            targets=[("ACCOUNT", saved.id)],
        )

        return saved

    @staticmethod
    def _has_company_name(company_name: str | None) -> bool:
        return bool(company_name and company_name.strip())

    # ======================================================
    # EXISTING ACCOUNT
    # ======================================================

    def _get_existing_account(
        self,
        account_id: UUID | None,
    ) -> Account:

        if account_id is None:
            raise ValueError(
                "account_id is required when using an existing Account."
            )

        account = self.account_repository.get_by_id(
            account_id,
        )

        if account is None:
            raise ValueError(
                "Selected Account not found."
            )

        if account.is_deleted:
            raise ValueError(
                "Cannot use a deleted Account."
            )

        return account

    # ======================================================
    # CONTACT
    # ======================================================

    def _create_contact(
        self,
        lead,
        account_id: UUID | None,
        data: ConvertLeadDTO,
        current_user_id: UUID,
    ) -> Contact:

        contact_data = data.contact

        # When contact data is not supplied by the frontend,
        # create the Contact from the Lead automatically.
        if contact_data is None:

            contact = Contact.create(
                account_id=account_id,
                contact_owner_id=lead.owner_id,
                name=lead.name,
                email=lead.email,
                secondary_email=None,
                phone=lead.phone,
                other_phone=None,
                mobile=lead.mobile_number,
                home_phone=None,
                assistant_phone=None,
                title=lead.title,
                department=None,
                lead_source=lead.lead_source.value,
                vendor_name=None,
                date_of_birth=None,
                assistant=None,
                email_opt_out=False,
                reporting_to_id=None,
                mailing_address=lead.address,
                mailing_city=lead.city,
                mailing_state=lead.state,
                mailing_country=lead.country,
                mailing_postal_code=lead.postal_code,
                other_address=None,
                description=lead.description,
                created_by_id=current_user_id,
            )

        else:

            contact = Contact.create(
                account_id=account_id,
                contact_owner_id=lead.owner_id,
                name=contact_data.name,
                email=contact_data.email,
                secondary_email=contact_data.secondary_email,
                phone=contact_data.phone,
                other_phone=contact_data.other_phone,
                mobile=contact_data.mobile,
                home_phone=contact_data.home_phone,
                assistant_phone=contact_data.assistant_phone,
                title=contact_data.title,
                department=contact_data.department,
                lead_source=contact_data.lead_source,
                vendor_name=contact_data.vendor_name,
                date_of_birth=contact_data.date_of_birth,
                assistant=contact_data.assistant,
                email_opt_out=contact_data.email_opt_out,
                reporting_to_id=contact_data.reporting_to_id,
                mailing_address=contact_data.mailing_address,
                mailing_city=contact_data.mailing_city,
                mailing_state=contact_data.mailing_state,
                mailing_country=contact_data.mailing_country,
                mailing_postal_code=contact_data.mailing_postal_code,
                other_address=contact_data.other_address,
                description=contact_data.description,
                created_by_id=current_user_id,
            )

        saved = self.contact_repository.save(contact)

        self.timeline_recorder.record(
            event_type="CONTACT_CREATED",
            actor_id=current_user_id,
            message=(
                f"Contact created by converting the Lead {lead.name}"
            ),
            metadata={
                "contact_id": str(saved.id),
                "contact_name": saved.name,
                "source": "LEAD_CONVERSION",
                "source_lead_id": str(lead.id),
                "source_lead_name": lead.name,
            },
            targets=[("CONTACT", saved.id)],
        )

        return saved

    def _get_existing_contact(
        self,
        contact_id: UUID | None,
    ) -> Contact:

        if contact_id is None:
            raise ValueError(
                "contact_id is required when using an existing Contact."
            )

        contact = self.contact_repository.get_by_id(
            contact_id,
        )

        if contact is None:
            raise ValueError(
                "Selected Contact not found."
            )

        if contact.is_deleted:
            raise ValueError(
                "Cannot use a deleted Contact."
            )

        return contact

    def _use_existing_contact(
        self,
        contact: Contact,
        account: Account | None,
    ) -> None:

        # If the Contact already belongs to an Account,
        # keep its existing Account.
        #
        # This follows Zoho-style lead conversion behavior:
        # an existing Contact's Account relationship should
        # not be silently changed during conversion.

        if contact.account_id is not None:
            return

        # Contact-only conversion must not attach the Contact to an
        # Account. If an Account is part of the conversion, associate
        # an unlinked existing Contact with that Account.
        if account is None:
            return

        contact.account_id = account.id

        self.contact_repository.save(contact)
