from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from src.modules.lead_capture.application.interfaces.lead_form_repository import (
    LeadFormRepository,
)
from src.modules.lead_capture.domain.entities.assignment_mode import AssignmentMode
from src.modules.lead_capture.domain.entities.lead_form import (
    DEFAULT_FORM_TITLE,
    FormOwner,
    LeadForm,
    generate_public_token,
)
from src.modules.lead_capture.infrastructure.persistence.django_lead_form_model import (
    DjangoLeadFormModel,
    DjangoLeadFormRotationOwnerModel,
)


class DjangoLeadFormRepository(LeadFormRepository):
    def __init__(self, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _queryset(self):
        # Every query is pinned to this company: that is the tenant boundary.
        return DjangoLeadFormModel.objects.filter(company_id=self._company_id)

    # ----------------------------------------------------------------- reads

    def create_default(self) -> LeadForm:
        model = DjangoLeadFormModel.objects.create(
            company_id=self._company_id,
            public_token=generate_public_token(),
            title=DEFAULT_FORM_TITLE,
            lead_source="",
            assignment_mode=DjangoLeadFormModel.AssignmentMode.SINGLE_OWNER,
            is_active=False,
        )
        return self._to_domain(model)

    def get(self) -> LeadForm:
        return self._to_domain(self._get_or_create_model(lock=False))

    def get_for_update(self) -> LeadForm:
        # Must run inside a transaction (the use case provides it).
        return self._to_domain(self._get_or_create_model(lock=True))

    def _get_or_create_model(self, *, lock: bool) -> DjangoLeadFormModel:
        def fetch():
            queryset = self._queryset().select_related("single_owner")
            if lock:
                # of=("self",): lock only the form row, not the joined user.
                queryset = queryset.select_for_update(of=("self",))
            return queryset.first()

        model = fetch()
        if model is not None:
            return model

        # Safety net: every company gets its form when it is created (and
        # by the backfill migration). If one is ever missing, make it now
        # instead of failing. A parallel request losing the race simply
        # reads the winner's row.
        try:
            with transaction.atomic():
                self.create_default()
        except IntegrityError:
            pass
        return fetch()

    # ---------------------------------------------------------------- writes

    def save(self, form: LeadForm) -> LeadForm:
        updated = self._queryset().filter(id=form.id).update(
            title=form.title,
            lead_source=form.lead_source,
            assignment_mode=form.assignment_mode.value,
            single_owner_id=form.single_owner.id if form.single_owner else None,
            public_token=form.public_token,
            is_active=form.is_active,
            last_assigned_position=form.last_assigned_position,
            # update() skips auto_now, so set it by hand.
            updated_at=timezone.now(),
        )
        if not updated:
            raise ValueError("Lead form not found.")

        self._replace_rotation(form)
        return self._to_domain(self._queryset().select_related("single_owner").get(id=form.id))

    def record_submission(
        self, form: LeadForm, assigned_position: int | None
    ) -> None:
        now = timezone.now()
        changes = {
            "submission_count": F("submission_count") + 1,
            "last_submission_at": now,
            "updated_at": now,
        }
        if assigned_position is not None:
            changes["last_assigned_position"] = assigned_position
        updated = self._queryset().filter(id=form.id).update(**changes)
        if not updated:
            raise ValueError("Lead form not found.")

    def _replace_rotation(self, form: LeadForm) -> None:
        wanted = [(o.id, index) for index, o in enumerate(form.rotation_owners)]
        current = list(
            DjangoLeadFormRotationOwnerModel.objects.filter(form_id=form.id)
            .order_by("position")
            .values_list("user_id", "position")
        )
        if current == wanted:
            return

        DjangoLeadFormRotationOwnerModel.objects.filter(form_id=form.id).delete()
        DjangoLeadFormRotationOwnerModel.objects.bulk_create(
            [
                DjangoLeadFormRotationOwnerModel(
                    form_id=form.id, user_id=user_id, position=position
                )
                for user_id, position in wanted
            ]
        )

    # --------------------------------------------------------------- mapping

    @staticmethod
    def _to_domain(model: DjangoLeadFormModel) -> LeadForm:
        entries = (
            DjangoLeadFormRotationOwnerModel.objects.filter(form_id=model.id)
            .select_related("user")
            .order_by("position")
        )
        owner = model.single_owner
        return LeadForm(
            id=model.id,
            company_id=model.company_id,
            public_token=model.public_token,
            title=model.title,
            lead_source=model.lead_source,
            assignment_mode=AssignmentMode(model.assignment_mode),
            single_owner=FormOwner(id=owner.id, name=owner.name) if owner else None,
            rotation_owners=[
                FormOwner(id=e.user_id, name=e.user.name, position=e.position)
                for e in entries
            ],
            is_active=model.is_active,
            last_assigned_position=model.last_assigned_position,
            submission_count=model.submission_count,
            last_submission_at=model.last_submission_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
