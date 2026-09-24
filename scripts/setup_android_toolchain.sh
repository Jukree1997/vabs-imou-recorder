#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$script_dir")
tool_dir="$project_dir/.tools"
jdk_dir="$tool_dir/jdk21"
sdk_dir="$tool_dir/android-sdk"
download_dir="$tool_dir/downloads"

mkdir -p "$tool_dir" "$download_dir" "$sdk_dir/cmdline-tools"

if [[ ! -x $jdk_dir/bin/java ]]; then
  echo "Downloading the latest Eclipse Temurin JDK 21..."
  metadata="$download_dir/temurin21.json"
  curl -fL \
    'https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture=x64&image_type=jdk&os=linux&vendor=eclipse' \
    -o "$metadata"
  mapfile -t release < <(python3 - "$metadata" <<'PY'
import json
import sys

assets = json.load(open(sys.argv[1], encoding="utf-8"))
package = assets[0]["binary"]["package"]
print(package["link"])
print(package["checksum"])
PY
  )
  jdk_archive="$download_dir/temurin21.tar.gz"
  curl -fL "${release[0]}" -o "$jdk_archive"
  printf '%s  %s\n' "${release[1]}" "$jdk_archive" | sha256sum -c -
  temporary=$(mktemp -d)
  trap 'rm -rf -- "$temporary"' EXIT
  tar -xzf "$jdk_archive" -C "$temporary"
  extracted=$(find "$temporary" -mindepth 1 -maxdepth 1 -type d -print -quit)
  if [[ -z $extracted ]]; then
    echo "The JDK archive had no top-level directory." >&2
    exit 1
  fi
  mv "$extracted" "$jdk_dir"
  rm -rf -- "$temporary"
  trap - EXIT
fi

command_tools="$sdk_dir/cmdline-tools/latest/bin/sdkmanager"
if [[ ! -x $command_tools ]]; then
  tools_archive="$download_dir/commandlinetools-linux-15859902_latest.zip"
  tools_sha256=4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583
  echo "Downloading Android command-line tools..."
  curl -fL \
    'https://dl.google.com/android/repository/commandlinetools-linux-15859902_latest.zip' \
    -o "$tools_archive"
  printf '%s  %s\n' "$tools_sha256" "$tools_archive" | sha256sum -c -
  temporary=$(mktemp -d)
  trap 'rm -rf -- "$temporary"' EXIT
  unzip -q "$tools_archive" -d "$temporary"
  mv "$temporary/cmdline-tools" "$sdk_dir/cmdline-tools/latest"
  rm -rf -- "$temporary"
  trap - EXIT
fi

echo
echo "Base tools are ready. Next, source scripts/android_env.sh and review"
echo "Google's Android SDK licenses with: sdkmanager --licenses"
