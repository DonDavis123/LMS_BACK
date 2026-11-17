from rest_framework import serializers

from src.modules.calls.domain.enums.transcription_status import TranscriptionStatus


class TranscriptSegmentSerializer(serializers.Serializer):
    speaker = serializers.CharField()
    timestamp = serializers.CharField(allow_null=True)
    text = serializers.CharField()


class RecordingTranscriptSerializer(serializers.Serializer):
    """Serializer for a ``RecordingTranscriptDTO``.

    A recording nobody asked to transcribe is answered with status
    ``NOT_REQUESTED`` and empty fields, so one URL can be polled.
    """

    recording_id = serializers.UUIDField()
    call_id = serializers.UUIDField()
    status = serializers.SerializerMethodField()
    language = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    key_points = serializers.SerializerMethodField()
    action_items = serializers.SerializerMethodField()
    transcript = serializers.SerializerMethodField()
    segments = serializers.SerializerMethodField()
    model = serializers.SerializerMethodField()
    error_message = serializers.SerializerMethodField()
    requested_by_id = serializers.SerializerMethodField()
    started_at = serializers.SerializerMethodField()
    completed_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()

    def _value(self, dto, attribute, default=None):
        transcript = dto.transcript
        return default if transcript is None else getattr(transcript, attribute)

    def get_status(self, dto) -> str:
        if dto.transcript is None:
            return TranscriptionStatus.NOT_REQUESTED.value
        return dto.transcript.status.value

    def get_language(self, dto):
        return self._value(dto, "language")

    def get_summary(self, dto):
        return self._value(dto, "summary")

    def get_key_points(self, dto):
        return list(self._value(dto, "key_points", []))

    def get_action_items(self, dto):
        return list(self._value(dto, "action_items", []))

    def get_transcript(self, dto):
        return self._value(dto, "transcript_text")

    def get_segments(self, dto):
        return [segment.to_dict() for segment in self._value(dto, "segments", [])]

    def get_model(self, dto):
        return self._value(dto, "model_name")

    def get_error_message(self, dto):
        return self._value(dto, "error_message")

    def get_requested_by_id(self, dto):
        value = self._value(dto, "requested_by_id")
        return None if value is None else str(value)

    def get_started_at(self, dto):
        return self._datetime(self._value(dto, "started_at"))

    def get_completed_at(self, dto):
        return self._datetime(self._value(dto, "completed_at"))

    def get_updated_at(self, dto):
        return self._datetime(self._value(dto, "updated_at"))

    @staticmethod
    def _datetime(value):
        return None if value is None else serializers.DateTimeField().to_representation(value)


class RequestTranscriptionSerializer(serializers.Serializer):
    # Run again even though a finished transcript exists.
    regenerate = serializers.BooleanField(required=False, default=False)
