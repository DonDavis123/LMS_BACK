from rest_framework import serializers

from src.modules.tasks.domain.enums.task_priority import TaskPriority
from src.modules.tasks.domain.enums.task_status import TaskStatus


class TaskSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    subject = serializers.CharField()
    due_date = serializers.DateField(allow_null=True)
    priority = serializers.ChoiceField(
        choices=[
            (priority.value, priority.value)
            for priority in TaskPriority
        ],
    )
    owner_id = serializers.UUIDField()
    reminder_at = serializers.DateTimeField(allow_null=True)
    lead_id = serializers.UUIDField(allow_null=True)
    contact_id = serializers.UUIDField(allow_null=True)
    account_id = serializers.UUIDField(allow_null=True)
    status = serializers.ChoiceField(
        choices=[
            (status.value, status.value)
            for status in TaskStatus
        ],
    )
    description = serializers.CharField(allow_null=True)
    created_by_id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
