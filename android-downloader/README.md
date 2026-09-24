# Android emulator downloader

This is a minimal, local-only companion for one IMOU SD-card recording. It
uses IMOU's official Android OpenSDK `startDeviceDownload` interface. The APK
does not contain the IMOU App Secret. Linux creates a private short-lived job,
the companion writes an MP4 in its private emulator storage, and Linux uses
debug-only `run-as` access to pull and validate that file before publishing it
to the VABS video tree.

IMOU's AAR is proprietary and intentionally ignored by Git. Install it from an
official SDK archive with:

```bash
scripts/install_imou_android_sdk.sh /path/to/imou-android-opensdk.rar
```

## One-time local setup

The project-local installation includes Java 21, matching the current IMOU AAR,
and does not modify system packages:

```bash
scripts/setup_android_toolchain.sh
source scripts/android_env.sh
sdkmanager --licenses
scripts/install_android_components.sh
scripts/start_android_emulator.sh
scripts/build_install_android.sh
```

`sdkmanager --licenses` is intentionally interactive so the operator can read
and accept Google's current Android SDK terms. The Android 11 Google APIs x86
image is used because it includes translation for ARM-only apps; the IMOU AAR
does not ship x86 or x86_64 native libraries.

## First one-clip proof

Add the camera-label security code to the private `.env` file:

```dotenv
IMOU_DEVICE_CODE=your-camera-label-security-code
VABS_TIME_ZONE=Asia/Bangkok
```

Then prepare the first chronological clip from a date and run it:

```bash
python3 -m imou_recorder.cli --prepare-android-job 2026-09-22
python3 -m imou_recorder.emulator
```

The prepared job is mode `0600` and is ignored by Git. It temporarily contains
an access token, play token, device ID, SD-card filename, and camera security
code. The companion removes its copy after a successful transfer, and the
Linux bridge removes the local job after the MP4 passes `ffprobe` validation.
