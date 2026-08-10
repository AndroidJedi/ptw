#!/usr/bin/env bash

set -euo pipefail

ptw_workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ptw_local_sdk="$(sed -n 's/^sdk.dir=//p' "$ptw_workspace/android/local.properties" | head -n 1)"
ptw_android_sdk="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$ptw_local_sdk}}"
ptw_adb="$ptw_android_sdk/platform-tools/adb"
ptw_emulator="$ptw_android_sdk/emulator/emulator"
ptw_device_id="emulator-5554"
ptw_avd_name="Pixel_9_Pro"
ptw_emulator_log="${TMPDIR:-/tmp}/ptw-android-emulator.log"

if [[ ! -x "$ptw_adb" || ! -x "$ptw_emulator" ]]; then
  echo "Android SDK tools were not found at: $ptw_android_sdk" >&2
  exit 1
fi

if [[ "$("$ptw_adb" -s "$ptw_device_id" get-state 2>/dev/null || true)" != "device" ]]; then
  echo "Starting Android emulator: $ptw_avd_name"
  nohup "$ptw_emulator" -avd "$ptw_avd_name" -no-snapshot-load \
    >"$ptw_emulator_log" 2>&1 &

  for ptw_attempt in {1..60}; do
    if [[ "$("$ptw_adb" -s "$ptw_device_id" get-state 2>/dev/null || true)" == "device" ]] &&
      [[ "$("$ptw_adb" -s "$ptw_device_id" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; then
      break
    fi
    if [[ "$ptw_attempt" == "60" ]]; then
      echo "Android emulator did not finish booting. See $ptw_emulator_log" >&2
      exit 1
    fi
    sleep 1
  done
fi

if [[ "${1:-}" == "--emulator-only" ]]; then
  exit 0
fi

cd "$ptw_workspace"
flutter pub get
dart run tool/ptw_template_mcp/sync.dart
exec flutter run --debug -d "$ptw_device_id"
