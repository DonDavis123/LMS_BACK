# Call recordings API

Why: after a call it is hard to remember what was said. A user can attach the
voice recording of a call (from a phone recorder, a call-recording app or the
browser) to the call and play it back later from the call detail.

All endpoints are tenant scoped, exactly like the other call endpoints: a
company only ever sees, plays, adds or deletes recordings of its own calls.
A call or recording of another company behaves like one that does not exist
(`404`).

Auth: JWT, company user (`IsAuthenticated` + `IsCompanyUser`).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/calls/<call_id>/recordings/` | Recordings of the call, newest first. |
| `POST` | `/api/calls/<call_id>/recordings/` | Upload one recording (`multipart/form-data`). |
| `DELETE` | `/api/calls/<call_id>/recordings/<recording_id>/` | Delete the recording and its audio file. |
| `GET` | `/api/calls/<call_id>/recordings/<recording_id>/file/` | Stream the audio (`?download=1` forces a download). |

## `POST /api/calls/<call_id>/recordings/`

`Content-Type: multipart/form-data`

| Field | Type | Rules |
|---|---|---|
| `file` | file, **required** | An audio file, not empty, at most `CALL_RECORDING_MAX_MB` (default 25 MB). |
| `duration_seconds` | integer, optional | `0`–`86400`. The client can read it from the audio before uploading. |

Accepted formats: `mp3`, `m4a`, `mp4`, `aac`, `wav`, `ogg`, `oga`, `opus`,
`webm`, `amr`, `3gp`, `flac`. The content type is taken from the upload; a
missing / generic one (`application/octet-stream`) is resolved from the file
extension. Anything that is not audio is refused, so HTML or script files can
never be stored.

Rules:

* The call must exist and be **completed**. A planned or missed call has not
  happened yet, so it has nothing to record.
* A call holds at most `CALL_RECORDING_MAX_PER_CALL` recordings (default 10).
* Recordings can be added to older calls of a record too; only editing the
  call itself is limited to the latest call.

`201` response:

```json
{
  "id": "7d0f...",
  "call_id": "41ab...",
  "file_name": "call-with-asha.mp3",
  "content_type": "audio/mpeg",
  "size_bytes": 1843200,
  "duration_seconds": 184,
  "uploaded_by_id": "9c2e...",
  "uploaded_by_name": "Call Owner",
  "created_at": "2026-11-12T09:30:00Z",
  "file_path": "/api/calls/41ab.../recordings/7d0f.../file/"
}
```

Errors use the usual `{"detail": "..."}` shape:

| Status | When |
|---|---|
| `400` | No file, empty file, not audio, over the size limit, too many recordings, call not completed, bad duration, or the overall recording storage is full (`Recording storage is full. ...`). |
| `404` | Unknown call (or a call of another company). |
| `413` | The request body is far larger than the size limit (refused before it is read). |

## `GET /api/calls/<call_id>/recordings/`

```json
{ "results": [ { "...same fields as above..." } ] }
```

## `GET .../recordings/<recording_id>/file/`

Returns the audio with its content type and `Content-Disposition: inline`
(`attachment` with `?download=1`). It answers for any `Accept` header.

The audio has **no public URL**: the response is `Cache-Control: private,
no-store` and `X-Content-Type-Options: nosniff`, and it needs the bearer token.
A plain `<audio src>` cannot send that header, so the client fetches the file
with its authenticated HTTP client as a blob and plays an object URL.

`404` when the call or recording does not exist, or when the file is no longer
in storage.

## Timeline

| `event_type` | When |
|---|---|
| `CALL_RECORDING_ADDED` | A recording was uploaded. Metadata: `call_id`, `recording_id`, `file_name`, `size_bytes`. |
| `CALL_RECORDING_DELETED` | A recording was deleted. Metadata: `call_id`, `recording_id`, `file_name`. |

Both are recorded on the call, its lead / contact and its account, and show up
in `/api/calls/<call_id>/history/` (their ids start with `CALL_`).

## Storage and configuration

Audio is saved under
`call_recordings/<company_id>/<call_id>/<recording_id>.<ext>` in the
`call_recordings` entry of `settings.STORAGES`; the database keeps only the
metadata (`call_recordings` table, a few hundred bytes per recording).

* **Production (Supabase):** a **private** Supabase Storage bucket, reached
  through Supabase's S3-compatible API (`django-storages` + `boto3`).
* **Local development:** the `MEDIA_ROOT` folder, when `SUPABASE_STORAGE_BUCKET`
  is not set.

| Environment variable | Default | Meaning |
|---|---|---|
| `SUPABASE_STORAGE_BUCKET` | empty | Bucket name. Setting it switches the storage to Supabase. |
| `SUPABASE_S3_ENDPOINT` | - | Required with a bucket. Copy it from Storage -> S3 Connection (looks like `https://<project-ref>.storage.supabase.co/storage/v1/s3`). |
| `SUPABASE_S3_REGION` | `us-east-1` | Region shown next to the endpoint. |
| `SUPABASE_S3_ACCESS_KEY_ID` | - | Required with a bucket (Storage -> S3 Connection -> New access key). |
| `SUPABASE_S3_SECRET_ACCESS_KEY` | - | Required with a bucket. Keep it secret, never commit it. |
| `MEDIA_ROOT` | `<project>/media` | Local folder, used only without a bucket. |
| `CALL_RECORDING_MAX_MB` | `25` | Largest accepted recording (Supabase free plan: 50 MB per file at most). |
| `CALL_RECORDING_MAX_PER_CALL` | `10` | Most recordings on one call. |
| `CALL_RECORDING_STORAGE_LIMIT_MB` | `900` with a bucket, `0` without | Most audio all companies together may keep. New uploads are refused with `400` once it would be exceeded. `0` = no limit. Keep it below the plan's 1 GB (1024 MB). |

### Supabase setup (once)

1. Dashboard -> **Storage** -> **New bucket**, e.g. `call-recordings`. Leave
   **Public bucket OFF**: recordings must only be reachable through the API.
2. Storage -> **S3 Connection**: note the endpoint and region, then create an
   access key. The S3 key works with the server only, so it never reaches the
   browser.
3. On Render add the five `SUPABASE_*` variables above and redeploy. The new
   `django-storages` and `boto3` packages are installed from `requirements.txt`.
4. Run the migration (`build.sh` already does): it only creates the small
   `call_recordings` table in your Supabase database.

The free plan gives 1 GB of storage in total, roughly 1,000 five-minute MP3
recordings; watch it under Storage -> Usage. Large phone recordings (WAV) fill
it quickly.

The backend enforces that budget itself: the sizes of all recordings (every
company, the bucket is shared) are added up before each upload, and an upload
that would pass `CALL_RECORDING_STORAGE_LIMIT_MB` is refused with a clear `400`
before anything is sent to Supabase. Deleting a recording frees its space
immediately. The check counts what the database knows about; audio that was
orphaned by a crash is not counted, which is why the default leaves ~12 %
headroom. The plan's separate 50 MB per-file cap is covered by
`CALL_RECORDING_MAX_MB`.

When a call is permanently deleted (for example when a retired user's calls
are cleaned up) its recordings are deleted with it, including the audio files.
Soft-deleted calls keep their recordings, but nobody can reach them.
