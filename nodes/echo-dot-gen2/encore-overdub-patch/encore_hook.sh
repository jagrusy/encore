#!/system/bin/sh
# Optional on-device webhook helper for rooted Echo Dot 2nd Gen (biscuit)
# Usage: encore_hook.sh <hub-ip> <node-id> [event] [prompt]

HUB_IP="${1:-192.168.1.50}"
NODE_ID="${2:-living-room-dot2}"
EVENT="${3:-action_button}"
PROMPT="${4:-}"

PAYLOAD="{\"source_node\":\"${NODE_ID}\",\"event\":\"${EVENT}\"}"
if [ -n "$PROMPT" ]; then
  PAYLOAD="{\"source_node\":\"${NODE_ID}\",\"event\":\"${EVENT}\",\"prompt\":\"${PROMPT}\"}"
fi

if command -v curl >/dev/null 2>&1; then
  curl -fsS -X POST "http://${HUB_IP}:8765/api/v1/ai/wake" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD"
else
  echo "curl not present on device; trigger via Home Assistant ESPHome automation -> POST http://${HUB_IP}:8765/api/v1/ai/wake"
fi
