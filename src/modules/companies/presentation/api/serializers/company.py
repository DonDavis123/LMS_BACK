from rest_framework import serializers

from src.modules.users.domain.entities.role import MANAGEABLE_ROLES

from src.modules.users.presentation.api.serializers.enum_value_field import (
    EnumValueField,
)


class CompanyListSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    website = serializers.CharField(read_only=True, allow_null=True)
    status = EnumValueField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    users_count = serializers.IntegerField(read_only=True)


class CompanyAdminSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)


class CompanyDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    website = serializers.CharField(read_only=True, allow_null=True)
    status = EnumValueField(read_only=True)
    status_reason = serializers.CharField(read_only=True)
    status_changed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    users_count = serializers.IntegerField(read_only=True)
    superadmins = CompanyAdminSerializer(many=True, read_only=True)


class CompanySerializer(serializers.Serializer):
    """Company as returned by create/update/suspend/activate."""

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    website = serializers.CharField(read_only=True, allow_null=True)
    status = EnumValueField(read_only=True)
    status_reason = serializers.CharField(read_only=True)
    status_changed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class CreateCompanySerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255)
    website = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    admin_name = serializers.CharField(max_length=150)
    admin_email = serializers.EmailField()
    admin_password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )


class UpdateCompanySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    website = serializers.URLField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one of name or website must be provided."
            )
        return attrs


class SuspendCompanySerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)


class CreateCompanyUserSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )
    role = serializers.ChoiceField(
        choices=[(role.value, role.name) for role in MANAGEABLE_ROLES],
    )


class PlatformAuditLogSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    action = EnumValueField(read_only=True)
    actor_id = serializers.UUIDField(read_only=True)
    actor_email = serializers.EmailField(read_only=True)
    company_id = serializers.UUIDField(read_only=True, allow_null=True)
    target_user_id = serializers.UUIDField(read_only=True, allow_null=True)
    target_email = serializers.CharField(read_only=True, allow_blank=True)
    metadata = serializers.JSONField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class RecentCompanySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    status = EnumValueField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
