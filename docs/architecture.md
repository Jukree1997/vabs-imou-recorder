# Architecture

## Components

### Backend coordinator

The backend owns the IMOU App Secret and performs signed OpenAPI requests. It
caches the administrator access token, discovers devices made available to the
developer account, queries local recording metadata one calendar day at a
time, and records download state in a local database.

### Android download companion

The Android component receives short-lived authorization and recording jobs
from the backend. It uses the official IMOU OpenSDK download interface to write
MP4 files and reports progress and completion. Long-running work should use an
Android foreground service so the operating system does not suspend an active
transfer.

The App Secret must never be embedded in the APK.

### Linux organizer

The organizer validates every completed file with `ffprobe`, rejects partial
or unreadable media, deduplicates by source recording ID, and publishes files
atomically into:

```text
{project}/{branch}/{camera}/{YYYY-MM}/{DD}/{HHMM-HHMM}.mp4
```

Clips are kept separate when the source timeline contains gaps. Concatenation
is safe only when codec parameters match and adjacent timestamps are verified
to be contiguous.

## Initial verification sequence

1. Obtain and cache an administrator access token.
2. Query bound and shared devices without modifying their ownership.
3. Check for local-storage and playback-by-filename capabilities.
4. Query one day of local recording metadata.
5. Download a single test clip through OpenSDK.
6. Validate the MP4 and confirm downstream processing accuracy.
7. Measure actual Open Platform flow charges before enabling scheduled bulk
   downloads.

## Secret boundaries

| Data | Backend | Android | GitHub |
|---|---:|---:|---:|
| App ID | Yes | Optional | No |
| App Secret | Yes | No | No |
| Temporary access token | Yes | Yes | No |
| Camera security code | Secret store only | Runtime only | No |
| Recording metadata | Yes | Job subset | No |
| Recorded MP4 | Configured storage | Temporary | No |

