from enum import Enum


class CallOutcome(str, Enum):
    CONNECTED = "Connected"
    NOT_ATTENDED = "Not Attended"
    BUSY = "Busy"
    VOICEMAIL = "Voicemail"
    WRONG_NUMBER = "Wrong Number"
    CALLBACK_REQUESTED = "Callback Requested"
