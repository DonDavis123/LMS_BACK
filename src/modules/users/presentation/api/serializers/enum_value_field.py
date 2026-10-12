from enum import Enum

from rest_framework import serializers


class EnumValueField(serializers.CharField):
    """Serialize an Enum member as its plain value (e.g. ``"ADMIN"``).

    ``str()`` of a ``str``-mixin Enum is ``"UserRole.ADMIN"`` on Python 3.11+,
    so a plain CharField would leak the member name into the API response.
    """

    def to_representation(self, value):
        if isinstance(value, Enum):
            value = value.value
        return super().to_representation(value)
