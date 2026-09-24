#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=android_env.sh
source "$script_dir/android_env.sh"

if adb devices | grep -q $'^emulator-.*\tdevice$'; then
  echo "An Android emulator is already connected."
  exit 0
fi

emulator -avd vabs-imou-api30 \
  -no-window \
  -no-audio \
  -no-boot-anim \
  -no-snapshot \
  -accel on \
  -gpu swiftshader_indirect \
  >"$ANDROID_USER_HOME/emulator.log" 2>&1 &

echo "Waiting for Android emulator..."
adb wait-for-device
until [[ $(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r') == 1 ]]; do
  sleep 2
done
adb shell input keyevent 82 >/dev/null
echo "Android emulator is ready."
