#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$script_dir")
# shellcheck source=android_env.sh
source "$script_dir/android_env.sh"

sdk_aar="$project_dir/android-downloader/app/libs/LCOpenSDK.aar"
if [[ ! -f $sdk_aar ]]; then
  echo "LCOpenSDK.aar is missing; run scripts/install_imou_android_sdk.sh first." >&2
  exit 2
fi

(
  cd "$project_dir/android-downloader"
  ./gradlew --no-daemon assembleDebug
)

apk="$project_dir/android-downloader/app/build/outputs/apk/debug/app-debug.apk"
adb install -r "$apk"
echo "Installed the VABS IMOU downloader in the emulator."
