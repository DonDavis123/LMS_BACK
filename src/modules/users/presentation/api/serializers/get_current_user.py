from rest_framework import serializers
from .enum_value_field import EnumValueField


class CurrentUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    role = EnumValueField()