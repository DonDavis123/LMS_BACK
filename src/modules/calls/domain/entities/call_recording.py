import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

MAX_FILE_NAME_LENGTH = 255
MAX_DURATION_SECONDS = 86400
DEFAULT_FILE_NAME = "recording"

# Audio formats a phone, a browser recorder or a call-recording app produces.
# File extension -> the content type the recording is stored and served with.
ALLOWED_EXTENSIONS: dict[str, str] = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".webm": "audio/webm",
    ".amr": "audio/amr",
    ".3gp": "audio/3gpp",
    ".flac": "audio/flac",
}

# Content types a client may declare. Anything else is refused, which keeps
# HTML / script uploads out of the store.
ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/x-m4a",
        "audio/m4a",
        "audio/aac",
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/ogg",
        "audio/opus",
        "audio/webm",
        "audio/amr",
        "audio/3gpp",
        "audio/flac",
        "audio/x-flac",
        "video/mp4",
        "video/webm",
    }
)

# Clients that cannot tell the type of a file send one of these.
GENERIC_CONTENT_TYPES: frozenset[str] = frozenset(
    {"", "application/octet-stream", "binary/octet-stream"}
)

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def normalise_content_type(content_type: str | None) -> str:
    """``Audio/WebM;codecs=opus`` -> ``audio/webm``."""
    return (content_type or "").split(";", 1)[0].strip().lower()


def clean_file_name(file_name: str | None) -> str:
    """The file name without any path part or control characters."""
    name = _CONTROL_CHARS.sub("", str(file_name or ""))
    name = name.replace("\\", "/").rsplit("/", 1)[-1].strip().strip(".")

    if not name:
        return DEFAULT_FILE_NAME

    if len(name) > MAX_FILE_NAME_LENGTH:
        stem, extension = os.path.splitext(name)
        name = stem[: MAX_FILE_NAME_LENGTH - len(extension)] + extension

    return name


def allowed_formats_label() -> str:
    return ", ".join(sorted(extension.lstrip(".") for extension in ALLOWED_EXTENSIONS))


@dataclass
class CallRecording:
    """A voice recording attached to one call.

    The audio itself lives in the recording storage under ``storage_key``;
    this entity only describes it.
    """

    id: UUID
    call_id: UUID
    uploaded_by_id: UUID | None
    file_name: str
    content_type: str
    size_bytes: int
    duration_seconds: int | None
    storage_key: str
    created_at: datetime

    @property
    def extension(self) -> str:
        return os.path.splitext(self.file_name)[1].lower()

    @staticmethod
    def resolve_content_type(file_name: str, declared: str | None) -> str:
        """The content type a recording is stored with.

        The declared type wins when it is an allowed audio type. A generic or
        missing type (phones and some browsers send
        ``application/octet-stream``) falls back to the file extension.
        """
        declared_type = normalise_content_type(declared)
        extension = os.path.splitext(file_name)[1].lower()

        if declared_type in ALLOWED_CONTENT_TYPES:
            return ALLOWED_EXTENSIONS.get(extension) or declared_type

        if declared_type in GENERIC_CONTENT_TYPES and extension in ALLOWED_EXTENSIONS:
            return ALLOWED_EXTENSIONS[extension]

        raise ValueError(
            "Unsupported recording format. "
            f"Upload an audio file ({allowed_formats_label()})."
        )

    def validate(self, *, max_size_bytes: int) -> None:
        if self.call_id is None:
            raise ValueError("Recording call is required.")

        if (
            isinstance(self.size_bytes, bool)
            or not isinstance(self.size_bytes, int)
            or self.size_bytes <= 0
        ):
            raise ValueError("The recording file is empty.")

        if self.size_bytes > max_size_bytes:
            raise ValueError(
                "The recording is larger than "
                f"{max_size_bytes // (1024 * 1024)} MB."
            )

        if self.duration_seconds is not None:
            if (
                isinstance(self.duration_seconds, bool)
                or not isinstance(self.duration_seconds, int)
                or not 0 <= self.duration_seconds <= MAX_DURATION_SECONDS
            ):
                raise ValueError(
                    "Recording duration must be between 0 and "
                    f"{MAX_DURATION_SECONDS} seconds."
                )

    @classmethod
    def create(
        cls,
        *,
        call_id: UUID,
        uploaded_by_id: UUID | None,
        file_name: str | None,
        content_type: str | None,
        size_bytes: int,
        max_size_bytes: int,
        duration_seconds: int | None = None,
    ) -> "CallRecording":
        name = clean_file_name(file_name)

        recording = cls(
            id=uuid4(),
            call_id=call_id,
            uploaded_by_id=uploaded_by_id,
            file_name=name,
            content_type=cls.resolve_content_type(name, content_type),
            size_bytes=size_bytes,
            duration_seconds=duration_seconds,
            # Set by the use case once the audio is stored.
            storage_key="",
            created_at=datetime.now(timezone.utc),
        )
        recording.validate(max_size_bytes=max_size_bytes)

        return recording
