from rest_framework import serializers


class ContactSerializer(serializers.Serializer):
    id = serializers.UUIDField()

    name = serializers.CharField()

    email = serializers.EmailField(allow_null=True)

    phone = serializers.CharField(allow_null=True)

    mobile = serializers.CharField(allow_null=True)

    account_id = serializers.UUIDField(allow_null=True)

    account_name = serializers.CharField(allow_null=True)

    contact_owner_id = serializers.UUIDField()

    contact_owner_name = serializers.CharField(allow_null=True)

    next_task_due_date = serializers.DateField(allow_null=True)

    next_task_status = serializers.CharField(allow_null=True)