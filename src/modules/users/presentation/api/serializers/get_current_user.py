from rest_framework import serializers
from .enum_value_field import EnumValueField


class CurrentUserCompanySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    status = serializers.CharField()


class CurrentUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    role = EnumValueField()
    google_email = serializers.EmailField(allow_null=True, required=False)
    mail_account_email = serializers.EmailField()
    company = CurrentUserCompanySerializer(allow_null=True, required=False)
