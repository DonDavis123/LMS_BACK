from rest_framework import serializers

from src.modules.calls.domain.entities.call_recording import MAX_DURATION_SECONDS


class UploadCallRecordingSerializer(serializers.Serializer):
    file = serializers.FileField()

    # Optional: the client can read the length of the audio it is uploading.
    duration_seconds = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        max_value=MAX_DURATION_SECONDS,
    )
