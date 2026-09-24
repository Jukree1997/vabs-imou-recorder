<p align="center">
  <img src="Group_85.png" alt="VABS PEOPLE" width="640">
</p>

# VABS IMOU Recorder

VABS IMOU Recorder is an internal video-ingestion project for authorized IMOU
cameras. Its goal is to discover recordings stored on a camera SD card through
the official IMOU Open Platform, download each recording as MP4, and organize
the result for the VABS video-processing pipeline.

> Status: early integration prototype. There is no downloadable APK release
> yet.

## Planned workflow

```text
Authorized IMOU camera SD card
            |
            | IMOU OpenAPI + Android OpenSDK
            v
Android download companion
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

The first milestone is a read-only OpenAPI probe that obtains an access token,
lists devices available through the linked IMOU account, checks SD-card
playback capabilities, and lists one day of recording metadata. Video download
will be added only after that capability check succeeds.

## Distribution

Android test builds and release notes will be published on the repository's
GitHub Releases page once the OpenSDK integration is ready.

## Legal

This project is intended only for cameras and recordings that the operator is
authorized to access. It is not affiliated with or endorsed by IMOU. IMOU and
related product names are trademarks of their respective owners. Use of the
IMOU Open Platform and OpenSDK is subject to IMOU's current terms and service
charges.

