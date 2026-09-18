from src.modules.leads.application.dto.update_lead import UpdateLeadDTO, _UNSET
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.timeline.application.services.change_tracker import build_field_changes
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class UpdateLeadUseCase:
    def __init__(
        self,
        lead_repository: LeadRepository,
        user_repository: UserRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.lead_repository = lead_repository
        self.user_repository = user_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, data: UpdateLeadDTO, current_user_id=None):
        existing_lead = self.lead_repository.get_by_id(data.lead_id)
        if existing_lead is None:
            raise ValueError("Lead not found.")

        updateable_fields = (
            "name", "title", "company_name", "email", "mobile_number", "phone",
            "lead_source", "lead_status", "industry", "rating", "website",
            "number_of_employees", "annual_revenue", "owner_id", "address", "city",
            "state", "country", "postal_code", "description",
        )
        old_values = {field: getattr(existing_lead, field) for field in updateable_fields}

        def update():
            if data.name is not _UNSET:
                existing_lead.name = data.name
            if data.title is not _UNSET:
                existing_lead.title = data.title
            if data.company_name is not _UNSET:
                existing_lead.company_name = data.company_name
            if data.email is not _UNSET:
                existing_lead.email = data.email
            if data.mobile_number is not _UNSET:
                existing_lead.mobile_number = data.mobile_number
            if data.phone is not _UNSET:
                existing_lead.phone = data.phone
            if data.lead_source is not _UNSET:
                existing_lead.lead_source = data.lead_source
            if data.lead_status is not _UNSET:
                existing_lead.lead_status = data.lead_status
            if data.industry is not _UNSET:
                existing_lead.industry = data.industry
            if data.rating is not _UNSET:
                existing_lead.rating = data.rating
            if data.website is not _UNSET:
                existing_lead.website = data.website
            if data.number_of_employees is not _UNSET:
                existing_lead.number_of_employees = data.number_of_employees
            if data.annual_revenue is not _UNSET:
                existing_lead.annual_revenue = data.annual_revenue

            if data.owner_id is not _UNSET:
                owner = self.user_repository.get_by_id(data.owner_id)
                if owner is None:
                    raise ValueError("Selected owner does not exist.")
                if not owner.is_active:
                    raise ValueError("Selected owner is inactive.")
                if owner.role not in {UserRole.ADMIN, UserRole.SUPERADMIN}:
                    raise ValueError("Selected owner must be an ADMIN or SUPERADMIN.")
                existing_lead.owner_id = data.owner_id

            if data.address is not _UNSET:
                existing_lead.address = data.address
            if data.city is not _UNSET:
                existing_lead.city = data.city
            if data.state is not _UNSET:
                existing_lead.state = data.state
            if data.country is not _UNSET:
                existing_lead.country = data.country
            if data.postal_code is not _UNSET:
                existing_lead.postal_code = data.postal_code
            if data.description is not _UNSET:
                existing_lead.description = data.description

            saved = self.lead_repository.save(existing_lead)
            new_values = {field: getattr(saved, field) for field in updateable_fields}
            changes = build_field_changes(old_values, new_values)

            if changes:
                if set(changes) == {"lead_status"}:
                    event_type = "LEAD_STATUS_CHANGED"
                    message = (
                        f"Lead status changed from "
                        f"{changes['lead_status']['old_value']} to "
                        f"{changes['lead_status']['new_value']}."
                    )
                else:
                    event_type = "LEAD_UPDATED"
                    message = f"Lead {saved.name} was updated."

                self.timeline_recorder.record(
                    event_type=event_type,
                    actor_id=current_user_id or saved.owner_id,
                    message=message,
                    metadata={"changes": changes},
                    targets=[("LEAD", saved.id)],
                )

            return saved

        return self.transaction_manager.execute(update)
