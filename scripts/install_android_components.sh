#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$script_dir")
# shellcheck source=android_env.sh
source "$script_dir/android_env.sh"

if [[ ! -x $ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager ]]; then
  echo "Run scripts/setup_android_toolchain.sh first." >&2
  exit 2
fi

sdkmanager --sdk_root="$ANDROID_SDK_ROOT" \
  "platform-tools" \
  "emulator" \
  "platforms;android-35" \
  "build-tools;35.0.0" \
  "system-images;android-30;google_apis;x86_64"

mkdir -p "$ANDROID_AVD_HOME"
if ! avdmanager list avd -c | grep -Fxq 'vabs-imou-api30'; then
  printf 'no\n' | avdmanager create avd \
    --force \
    --name vabs-imou-api30 \
    --package "system-images;android-30;google_apis;x86_64" \
    --device pixel_4
fi

echo "Android components and AVD vabs-imou-api30 are ready."
