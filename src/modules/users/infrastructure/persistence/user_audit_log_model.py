import uuid

from django.db import models


class DjangoUserAuditLogModel(models.Model):
    # Actor/target are stored as plain ids plus email snapshots (no FK) so
    # the audit trail is never affected by changes to the users table.
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    action = models.CharField(max_length=50, db_index=True)
    actor_id = models.UUIDField(db_index=True)
    actor_email = models.EmailField()
    target_user_id = models.UUIDField(db_index=True)
    target_email = models.EmailField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "user_audit_logs"
        ordering = ["-created_at"]
