#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/official-imou-android-opensdk.rar" >&2
  exit 2
fi

archive=$1
if [[ ! -f $archive ]]; then
  echo "Archive not found: $archive" >&2
  exit 2
fi
if ! command -v unrar >/dev/null 2>&1; then
  echo "The 'unrar' command is required to unpack IMOU's official SDK archive." >&2
  exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$script_dir")
destination="$project_dir/android-downloader/app/libs/LCOpenSDK.aar"
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT

unrar x -idq "$archive" "$temporary/"
source_aar=$(find "$temporary" -type f -name LCOpenSDK.aar -print -quit)
if [[ -z $source_aar ]]; then
  echo "LCOpenSDK.aar was not found in the supplied archive." >&2
  exit 1
fi

install -m 0600 "$source_aar" "$destination"
echo "Installed LCOpenSDK.aar locally (ignored by Git)."
