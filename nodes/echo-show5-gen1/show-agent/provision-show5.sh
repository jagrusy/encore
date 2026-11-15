#!/usr/bin/env bash
set -euo pipefail

NODE_ID="${1:-office-show5}"
HUB_IP="${2:-192.168.1.50}"
BRAIN_PORT="${3:-8765}"
KIOSK_URL="http://${HUB_IP}:${BRAIN_PORT}/ui/show5.html?node=${NODE_ID}"

echo "=== Provisioning Echo Show 5 1st Gen (checkers) '$NODE_ID' ==="

if ! command -v adb >/dev/null 2>&1; then
  echo "Error: 'adb' is required (Android platform-tools)." >&2
  exit 1
fi

adb wait-for-device

echo "1. Keeping display awake while plugged into AC power..."
adb shell settings put global stay_on_while_plugged_in 3

echo "2. Disabling lockscreen animations for snappy camera alerts..."
adb shell settings put global window_animation_scale 0
adb shell settings put global transition_animation_scale 0

echo "3. Opening Encore Show 5 Kiosk Dashboard ($KIOSK_URL)..."
adb shell am start -a android.intent.action.VIEW -d "$KIOSK_URL" || true

echo ""
echo "Next manual steps on this Echo Show 5 (LineageOS 18.1):"
echo "  1) Install Fully Kiosk Browser (or pin the browser) pointing to: $KIOSK_URL"
echo "  2) Install AirMusic / AirReceiver or Sendspin Android client to expose '$NODE_ID' as a synchronized audio sink."
echo "  3) Optionally pair a nearby 3rd-Gen Echo Dot in Android Bluetooth Settings to relay audio into the next room."
