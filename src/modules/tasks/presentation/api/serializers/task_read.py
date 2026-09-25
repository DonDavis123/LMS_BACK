from rest_framework import serializers


class TaskReadSerializer(serializers.Serializer):
    """Serializer for task read endpoints.

    Relationship IDs are retained for backwards compatibility while display
    names are exposed so clients do not have to render UUIDs as human-readable
    record names.
    """

    id = serializers.UUIDField(source="task.id")
    subject = serializers.CharField(source="task.subject")
    due_date = serializers.DateField(source="task.due_date", allow_null=True)
    priority = serializers.CharField(source="task.priority.value")
    owner_id = serializers.UUIDField(source="task.owner_id")
    reminder_at = serializers.DateTimeField(source="task.reminder_at", allow_null=True)

    lead_id = serializers.UUIDField(source="task.lead_id", allow_null=True)
    lead_name = serializers.CharField(allow_null=True)

    contact_id = serializers.UUIDField(source="task.contact_id", allow_null=True)
    contact_name = serializers.CharField(allow_null=True)

    account_id = serializers.UUIDField(source="task.account_id", allow_null=True)
    account_name = serializers.CharField(allow_null=True)

    status = serializers.CharField(source="task.status.value")
    description = serializers.CharField(source="task.description", allow_null=True)
    created_by_id = serializers.UUIDField(source="task.created_by_id")
    created_at = serializers.DateTimeField(source="task.created_at")
    updated_at = serializers.DateTimeField(source="task.updated_at")
