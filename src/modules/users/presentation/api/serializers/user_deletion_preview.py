from rest_framework import serializers


class _PreviewUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()


class _ImpactSerializer(serializers.Serializer):
    leads = serializers.IntegerField()
    contacts = serializers.IntegerField()
    accounts = serializers.IntegerField()
    tasks = serializers.IntegerField()
    meetings = serializers.IntegerField()
    reminders = serializers.IntegerField()
    notifications = serializers.IntegerField()
    timeline = serializers.IntegerField()


class _TransferRequiredSerializer(serializers.Serializer):
    leads = serializers.BooleanField()
    contacts = serializers.BooleanField()
    accounts = serializers.BooleanField()
    meetings = serializers.BooleanField()


class _PermanentDeletionsSerializer(serializers.Serializer):
    tasks = serializers.IntegerField()
    reminders = serializers.IntegerField()
    notifications = serializers.IntegerField()


class _UserActionSerializer(serializers.Serializer):
    type = serializers.CharField()


class UserDeletionPreviewSerializer(serializers.Serializer):
    user = _PreviewUserSerializer()
    impact = _ImpactSerializer()
    transfer_required = _TransferRequiredSerializer()
    permanent_deletions = _PermanentDeletionsSerializer()
    user_action = _UserActionSerializer()
    can_retire = serializers.BooleanField()
    blockers = serializers.ListField(child=serializers.CharField())
    has_related_data = serializers.BooleanField()
    user_is_blocked = serializers.BooleanField()
    available_actions = serializers.ListField(child=serializers.CharField())
