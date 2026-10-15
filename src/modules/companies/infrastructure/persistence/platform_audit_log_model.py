import uuid

from django.db import models


class PlatformAuditLogModel(models.Model):

    class Action(models.TextChoices):
        COMPANY_CREATED = "COMPANY_CREATED", "Company created"
        COMPANY_UPDATED = "COMPANY_UPDATED", "Company updated"
        COMPANY_SUSPENDED = "COMPANY_SUSPENDED", "Company suspended"
        COMPANY_ACTIVATED = "COMPANY_ACTIVATED", "Company activated"
        COMPANY_USER_CREATED = "COMPANY_USER_CREATED", "Company user created"
        COMPANY_USER_PASSWORD_RESET = (
            "COMPANY_USER_PASSWORD_RESET",
            "Company user password reset",
        )
        COMPANY_USER_BLOCKED = "COMPANY_USER_BLOCKED", "Company user blocked"
        COMPANY_USER_UNBLOCKED = "COMPANY_USER_UNBLOCKED", "Company user unblocked"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    action = models.CharField(max_length=50, choices=Action.choices)
    # Plain ids (no foreign keys) so the trail survives any later change.
    actor_id = models.UUIDField()
    actor_email = models.EmailField()
    company_id = models.UUIDField(null=True, blank=True)
    target_user_id = models.UUIDField(null=True, blank=True)
    target_email = models.EmailField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["company_id", "created_at"],
                name="platform_audit_company_idx",
            ),
            models.Index(fields=["action"], name="platform_audit_action_idx"),
        ]
