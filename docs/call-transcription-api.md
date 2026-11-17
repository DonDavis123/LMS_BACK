# Call transcription and summary (Google Gemini)

Why: a recorded call is only useful if someone listens to it. After a recording
is uploaded the backend sends the audio to the Google Gemini API, which returns
a speaker-labelled **transcript** and a **summary** (key points and action
items included) in a single request. Both are stored and shown with the
recording.

Same rules as the other call endpoints: JWT, company user
(`IsAuthenticated` + `IsCompanyUser`), tenant scoped. A recording of another
company behaves like one that does not exist (`404`).

## How it works

1. A recording is uploaded (`POST /api/calls/<call_id>/recordings/`). Unless
   `CALL_TRANSCRIPTION_AUTO=False` or no key is set, the transcription is queued
   right after the upload is saved. The upload response is unchanged.
2. A background worker (a small in-process thread pool) reads the audio from the
   recording storage and calls Gemini. The HTTP request never waits for it.
3. The client polls `GET .../transcript/` until `status` is `COMPLETED` or
   `FAILED`. Typical time: well under a minute for a few minutes of audio.

A failed transcription never fails an upload, and never touches the recording.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/calls/<call_id>/recordings/<recording_id>/transcript/` | Current transcript / summary / status. |
| `POST` | `/api/calls/<call_id>/recordings/<recording_id>/transcript/` | Start it (recordings that were not transcribed automatically), retry a failed one, or regenerate. |

Deleting a recording deletes its transcript. A recording has at most one.

### `GET`

Always `200` for an existing recording, so one URL can be polled:

```json
{
  "recording_id": "7d0f...",
  "call_id": "41ab...",
  "status": "COMPLETED",
  "language": "Malayalam",
  "summary": "Asha called to follow up on the quote ...",
  "key_points": ["Quote sent last week", "Customer wants a discount"],
  "action_items": ["Send revised quote by Friday"],
  "transcript": "[00:02] Agent: ...\n[00:09] Customer: ...",
  "segments": [
    { "speaker": "Agent", "timestamp": "00:02", "text": "..." },
    { "speaker": "Customer", "timestamp": "00:09", "text": "..." }
  ],
  "model": "gemini-2.5-flash",
  "error_message": null,
  "requested_by_id": "9c2e...",
  "started_at": "2026-11-17T09:30:02Z",
  "completed_at": "2026-11-17T09:30:31Z",
  "updated_at": "2026-11-17T09:30:31Z"
}
```

| `status` | Meaning |
|---|---|
| `NOT_REQUESTED` | Nobody asked to transcribe this recording. All other fields are empty. |
| `PENDING` | Queued. |
| `PROCESSING` | Gemini is working on it. |
| `COMPLETED` | `transcript`, `segments`, `summary`, `key_points`, `action_items`, `language` are filled. |
| `FAILED` | `error_message` says why in words that are safe to show to a user. |

`segments[].timestamp` is `MM:SS` from the start of the audio, or `null` when
the model did not give a usable one. `transcript` is the same content as one
text block, ready to copy.

### `POST`

Body (JSON, optional): `{ "regenerate": true }`.

| Situation | Result |
|---|---|
| Nothing yet, or the last attempt `FAILED` | Queued. `202`. |
| Already `PENDING` / `PROCESSING` | Nothing new is started. `202` with the current state. |
| Already `COMPLETED` | Returned as it is. `200`. Send `regenerate: true` to run it again (costs another Gemini request). |
| `PENDING` / `PROCESSING` for longer than `CALL_TRANSCRIPTION_STALE_MINUTES` | Treated as abandoned (the server restarted mid-run) and queued again. `202`. |

Errors use the usual `{"detail": "..."}` shape: `404` for an unknown call or
recording (or one of another company), `503` when `GEMINI_API_KEY` is not set.

## Configuration

| Environment variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | empty | Gemini API key (Google AI Studio -> Get API key). **Empty switches the feature off.** Keep it secret, never commit it. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Any Gemini model that accepts audio input. Change it here when Google retires or replaces it, no code change. |
| `GEMINI_TIMEOUT_SECONDS` | `300` | Seconds one Gemini request may take. |
| `GEMINI_MAX_RETRIES` | `2` | Extra attempts after a `429`, `5xx` or network error. |
| `GEMINI_MAX_OUTPUT_TOKENS` | `32768` | Cap for the answer (the transcript is the bulk of it). |
| `CALL_TRANSCRIPTION_AUTO` | `True` | Transcribe every new upload automatically. `False` = only on `POST`. |
| `CALL_TRANSCRIPTION_SUMMARY_LANGUAGE` | `English` | Language of the summary, key points and action items. The transcript always stays in the language that was spoken. |
| `CALL_TRANSCRIPTION_WORKERS` | `2` | Transcriptions that may run at once per server process. |
| `CALL_TRANSCRIPTION_STALE_MINUTES` | `15` | After this long an unfinished run counts as abandoned. |
| `CALL_TRANSCRIPTION_RUN_INLINE` | `False` | Run inside the request. Local debugging only. |

### Setup (once)

1. Create an API key in Google AI Studio.
2. On Render add `GEMINI_API_KEY` (and any other variable above) and redeploy.
3. Run the migration (`build.sh` already does): it creates the
   `call_recording_transcripts` table.

No new Python package is needed: the Gemini REST API is called with `requests`,
which is already in `requirements.txt`.

## Gemini details worth knowing

* Audio up to 14 MB is sent inside the request (Gemini caps a whole inline
  request at 20 MB, and base64 adds a third). Larger audio, up to the 25 MB
  upload limit, goes through the Gemini Files API and is deleted from Google
  again right after the transcription.
* The key travels in the `x-goog-api-key` header, never in a URL.
* Formats Gemini documents: `mp3`, `wav`, `aac`, `ogg`, `flac`, plus `m4a`. A
  format Gemini cannot decode (for example `amr` / `3gp` phone recordings) ends
  as `FAILED` with "The audio may be corrupt or in an unsupported format.";
  the recording itself stays playable.
* One request returns transcript and summary together, so a recording costs one
  model call.

## Privacy

Call audio is sent to Google. On Gemini's free tier Google may use submitted
content to improve its products; the paid tier does not. Calls contain customer
names and phone numbers, so use a billed key in production, and check that your
customers are told their calls may be recorded and processed.

## Limits of the background worker

The worker is a thread pool inside the web process (no Celery / Redis to run on
Render). Queued work lives in memory, so a deploy or crash drops it: that
transcript stays `PENDING` / `PROCESSING` until
`CALL_TRANSCRIPTION_STALE_MINUTES` passes, then `POST` (or the client's retry
button) queues it again. If this becomes a problem, implement the
`TranscriptionDispatcher` interface with a real task queue; no use case changes.
