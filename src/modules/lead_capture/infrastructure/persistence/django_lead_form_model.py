import uuid

from django.conf import settings
from django.db import models


class DjangoLeadFormModel(models.Model):
    """The public "contact us" form of a company (exactly one per company)."""

    class AssignmentMode(models.TextChoices):
        SINGLE_OWNER = "SINGLE_OWNER", "Single owner"
        ROTATION = "ROTATION", "Rotation"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # One form per company. Deleting a company deletes its form.
    company = models.OneToOneField(
        "companies.DjangoCompanyModel",
        on_delete=models.CASCADE,
        related_name="+",
    )

    # Part of the public link. Always generated explicitly with
    # secrets.token_urlsafe(24); there is deliberately no model default.
    public_token = models.CharField(max_length=64, unique=True)

    title = models.CharField(max_length=150, default="Contact us")

    # An option of the company's "Lead Source" picklist, or "" if not chosen.
    lead_source = models.CharField(max_length=100, blank=True, default="")

    assignment_mode = models.CharField(
        max_length=20,
        choices=AssignmentMode.choices,
        default=AssignmentMode.SINGLE_OWNER,
    )

    single_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    rotation_owners = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="DjangoLeadFormRotationOwnerModel",
        related_name="+",
    )

    # Position of the owner who got the last lead (for Part 2's rotation).
    last_assigned_position = models.PositiveIntegerField(null=True, blank=True)

    # False = blocked. New forms start blocked until configured.
    is_active = models.BooleanField(default=False)

    submission_count = models.PositiveIntegerField(default=0)
    last_submission_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lead_capture_forms"

    def __str__(self):
        return f"Lead form of company {self.company_id}"


class DjangoLeadFormRotationOwnerModel(models.Model):
    """One owner in a form's rotation, with its place in the order."""

    form = models.ForeignKey(
        DjangoLeadFormModel,
        on_delete=models.CASCADE,
        related_name="rotation_entries",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )
    position = models.PositiveIntegerField()

    class Meta:
        db_table = "lead_capture_rotation_owners"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["form", "user"],
                name="uniq_lead_form_rotation_user",
            ),
        ]
