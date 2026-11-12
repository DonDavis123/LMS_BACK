from rest_framework import serializers

from src.modules.accounts.domain.entities.account_document import (
    MAX_NAME_LENGTH,
    MAX_URL_LENGTH,
)


class AccountDocumentInputSerializer(serializers.Serializer):
    """Body of add (POST) and update (PUT). Format rules live in the domain."""

    name = serializers.CharField(max_length=MAX_NAME_LENGTH)
    url = serializers.CharField(max_length=MAX_URL_LENGTH)


class AccountDocumentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    account_id = serializers.UUIDField()
    name = serializers.CharField()
    url = serializers.CharField()
    created_by_id = serializers.UUIDField()
    created_by_name = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()
    modified_by_id = serializers.UUIDField()
    updated_at = serializers.DateTimeField()
