#!/usr/bin/env bash
# Source this file before using the local Android build/emulator tools.

vabs_script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
vabs_project_dir=$(dirname -- "$vabs_script_dir")

export JAVA_HOME="$vabs_project_dir/.tools/jdk21"
export ANDROID_SDK_ROOT="$vabs_project_dir/.tools/android-sdk"
export ANDROID_HOME="$ANDROID_SDK_ROOT"
export ANDROID_USER_HOME="$vabs_project_dir/.android"
export ANDROID_AVD_HOME="$ANDROID_USER_HOME/avd"
export GRADLE_USER_HOME="$vabs_project_dir/.tools/gradle-home"
export PATH="$JAVA_HOME/bin:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:$PATH"

unset vabs_script_dir vabs_project_dir
