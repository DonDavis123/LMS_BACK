from rest_framework import serializers


class CallRecordingSerializer(serializers.Serializer):
    """Serializer for a ``GetCallRecordingDTO``.

    ``file_path`` is the authenticated endpoint that streams the audio. The
    audio has no public URL, so the client fetches it with its bearer token.
    """

    id = serializers.UUIDField(source="recording.id")
    call_id = serializers.UUIDField(source="recording.call_id")
    file_name = serializers.CharField(source="recording.file_name")
    content_type = serializers.CharField(source="recording.content_type")
    size_bytes = serializers.IntegerField(source="recording.size_bytes")
    duration_seconds = serializers.IntegerField(
        source="recording.duration_seconds",
        allow_null=True,
    )
    uploaded_by_id = serializers.UUIDField(
        source="recording.uploaded_by_id",
        allow_null=True,
    )
    uploaded_by_name = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField(source="recording.created_at")
    file_path = serializers.SerializerMethodField()

    def get_file_path(self, dto) -> str:
        return (
            f"/api/calls/{dto.recording.call_id}"
            f"/recordings/{dto.recording.id}/file/"
        )
