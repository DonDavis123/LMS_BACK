from rest_framework import serializers

from src.modules.tasks.domain.enums.task_priority import TaskPriority
from src.modules.tasks.domain.enums.task_status import TaskStatus


class UpdateTaskSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255, required=False)
    due_date = serializers.DateField(required=False, allow_null=True)
    priority = serializers.ChoiceField(
        choices=[
            (priority.value, priority.value)
            for priority in TaskPriority
        ],
        required=False,
    )
    owner_id = serializers.UUIDField(required=False)
    reminder_at = serializers.DateTimeField(required=False, allow_null=True)
    lead_id = serializers.UUIDField(required=False, allow_null=True)
    contact_id = serializers.UUIDField(required=False, allow_null=True)
    account_id = serializers.UUIDField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=[
            (status.value, status.value)
            for status in TaskStatus
        ],
        required=False,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
