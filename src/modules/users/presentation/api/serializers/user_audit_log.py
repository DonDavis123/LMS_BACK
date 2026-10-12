from rest_framework import serializers
from .enum_value_field import EnumValueField


class UserAuditLogSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    action = EnumValueField(read_only=True)
    actor_id = serializers.UUIDField(read_only=True)
    actor_email = serializers.EmailField(read_only=True)
    target_user_id = serializers.UUIDField(read_only=True)
    target_email = serializers.EmailField(read_only=True)
    metadata = serializers.DictField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
