<p align="center">
  <img src="Group_85.png" alt="VABS PEOPLE" width="640">
</p>

# VABS IMOU Recorder

VABS IMOU Recorder is an internal video-ingestion project for authorized IMOU
cameras. Its goal is to discover recordings stored on a camera SD card through
the official IMOU Open Platform, download each recording as MP4, and organize
the result for the VABS video-processing pipeline.

> Status: working one-clip prototype. Device discovery, SD-card metadata
> queries, Android-emulator download, ADB transfer, and `ffprobe` validation
> have completed successfully; there is no downloadable APK release yet.

## Planned workflow

```text
Authorized IMOU camera SD card
            |
            | IMOU OpenAPI + Android OpenSDK
            v
Local Android emulator companion
            |
            | authenticated upload/sync
            v
Linux organizer and validation service
            |
            v
{project}/{branch}/{camera}/{YYYY-MM}/{DD}/{HHMM-HHMM}.mp4
```

Short event recordings remain separate unless they are verified to be
contiguous. This preserves the original recording timeline for downstream
analytics.

## Intended capabilities

- Discover authorized devices without exposing device credentials.
- Query SD-card recording metadata incrementally.
- Download each unseen recording through the official IMOU OpenSDK.
- Resume interrupted transfers and avoid duplicate downloads.
- Validate completed MP4 files with `ffprobe`.
- Normalize files into the folder and filename convention expected by the
  VABS processing application.
- Keep developer secrets on the backend instead of embedding them in the
  Android application.

## Repository safety

Never commit any of the following:

- IMOU App Secret or access tokens
- camera serial numbers, QR codes, passwords, or security codes
- customer names, locations, or camera configuration exports
- recorded video, thumbnails, logs, or database files

Use `.env.example` only as a field reference. Real values belong in a local
`.env` file or a production secret manager.

## Development status

The read-only OpenAPI milestone obtains an access token, lists devices available
through the linked Imou Life account, checks SD-card playback capabilities, and
lists one day of recording metadata. The one-clip milestone now downloads and
validates a short recording through the project-local Android emulator
companion. The next milestone is resumable incremental batch ingestion.

### Run the first read-only probe

Create a private `.env` from `.env.example`, fill the IMOU App ID, App Secret,
and account data-center hostname, then run:

```bash
python3 -m unittest discover -s tests -v
python3 -m imou_recorder.cli
```

The probe performs only read-only OpenAPI calls: `accessToken`,
`deviceBaseList`, and `deviceBaseDetailList`. It does not bind, unbind,
configure, or download from a camera. Access tokens are kept in memory, App
Secrets are never printed, and device identifiers are masked in terminal
output.

After the basic probe succeeds, query one day of SD-card metadata without
downloading video:

```bash
python3 -m imou_recorder.cli --records-date 2026-09-24
```

The metadata probe reads all pages for that date in batches of 30. It prints a
short time-range summary and never prints the camera's internal SD-card
filenames. The administrator token is cached at `.state/access_token.json`
with owner-only permissions so scheduled checks reuse IMOU's three-day token.

### Run the one-clip emulator proof

No spare Android phone is required. The Linux machine has KVM support, and the
companion uses an Android 11 Google APIs emulator image capable of running the
ARM native libraries shipped in IMOU's SDK. Follow the one-time setup and
one-clip procedure in [android-downloader/README.md](android-downloader/README.md).

Keep `IMOU_DEVICE_CODE` only in the private `.env`; this is the security code
printed on the camera label, not the Imou Life account password. The first
proof intentionally selects a single clip, validates it with `ffprobe`, and
only then publishes it into the configured VABS video directory.

Current IMOU documentation specifies `hmac-sha256` request signing. Some older
endpoint examples still contain legacy MD5 signatures; set
`IMOU_SIGNING_ALGORITHM=md5` only if the assigned data-center endpoint
explicitly rejects the current format.

## Distribution

Android test builds and release notes will be published on the repository's
GitHub Releases page once the OpenSDK integration is ready.

## Legal

This project is intended only for cameras and recordings that the operator is
authorized to access. It is not affiliated with or endorsed by IMOU. IMOU and
related product names are trademarks of their respective owners. Use of the
IMOU Open Platform and OpenSDK is subject to IMOU's current terms and service
charges.
