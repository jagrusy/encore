#!/usr/bin/env bash
set -euo pipefail

DOT_NAME="${1:-living-room-dot}"
HUB_IP="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OVERDUB_DIR="$SCRIPT_DIR/overdub"

echo "=== Provisioning Echo Dot 2nd Gen (biscuit) as '$DOT_NAME' ==="

if ! command -v adb >/dev/null 2>&1; then
  echo "Error: 'adb' is required (Android platform-tools)." >&2
  exit 1
fi

echo "1. Checking ADB connection..."
adb wait-for-device
adb devices -l

echo "2. Building & installing vendored Overdub (Go + Android NDK)..."
python3 "$OVERDUB_DIR/deploy/install.py" "$DOT_NAME"

echo "3. Pushing Encore hook helper to /data/local/bin/encore_hook.sh..."
adb push "$SCRIPT_DIR/encore-overdub-patch/encore_hook.sh" /data/local/tmp/encore_hook.sh
adb shell "su -c 'mv /data/local/tmp/encore_hook.sh /data/local/bin/encore_hook.sh && chmod 755 /data/local/bin/encore_hook.sh'"

if [[ -n "$HUB_IP" ]]; then
  echo "4. Testing connectivity to Encore Brain at http://$HUB_IP:8765/health..."
  adb shell "su -c '/data/local/bin/encore_hook.sh $HUB_IP $DOT_NAME provision_check'" || true
fi

echo "Done! Pair this Dot to Music Assistant (Sendspin) using the token printed above."
