# Project Encore

**A second act for retired hardware.** Project Encore unifies a Linux **Surface Pro 3** hub, a **Google Nest Hub**, unlocked **Echo Dot 2nd Gen (`biscuit`)** and **Echo Show 5 1st Gen (`checkers`)** smart nodes, and offline **Echo Dot 3rd Gen (`donut`) / Echo 2nd Gen (`radar`)** Bluetooth satellites into a single self-hosted multi-room audio, HomeKit camera, and AI agent mesh.

## Architecture

- **Hub (`hub/` — Surface Pro 3, 8GB RAM, 256GB SSD, Intel QuickSync):**
  - **Music Assistant**: Central synchronized multi-room engine speaking Google Cast (Kitchen Nest Hub), Sendspin (Overdub & Show 5s), and AirPlay 2.
  - **AirConnect (`hub/airconnect/`)**: Bridges your Kitchen Nest Hub and existing Google Cast speaker groups into native AirPlay targets.
  - **`go2rtc` (`hub/cameras/`)**: Hardware-accelerated Intel VA-API RTSP-to-HomeKit camera bridge + low-latency WebRTC feeds.
  - **`bt-multi-sink` (`hub/bt-multi-sink/`)**: Keeps Bluetooth A2DP connections alive to nearby locked Echos and exposes each as an individual `shairport-sync` AirPlay speaker.
  - **`encore-brain` (`hub/encore-brain/`)**: FastAPI + WebSocket orchestrator routing AI Agent wakes and camera motion pop-ups to the Echo Show 5 displays.
- **Smart Nodes (`nodes/`):**
  - **Echo Dot 2nd Gen (`nodes/echo-dot-gen2/`)**: Vendored `firebreak` USB unlock + customized `overdub` (Sendspin + ESPHome + Encore AI webhook).
  - **Echo Show 5 1st Gen (`nodes/echo-show5-gen1/`)**: Vendored `amonet-checkers` BootROM unlock + `show-agent` 5.5" kiosk dashboard with live WebRTC camera overlay.
- **Shared & Lockfile:**
  - `shared/aiosendspin/`: Vendored Sendspin Python protocol library.
  - `UPSTREAM.lock.json`: Exact commit SHAs and source URLs of every vendored open-source project.

## Quick Start

### One-Command Surface Pro 3 Bootstrap

Run this once on your Linux Surface Pro 3 to install Docker, tune 24/7 power/lid settings, configure PipeWire/WirePlumber for Bluetooth A2DP speaker output, lock down UFW to your local LAN, clone this repo to `/opt/encore`, install Antigravity CLI (`agy`), and join your Tailscale mesh (`encore-sp3`):

```bash
curl -fsSL https://raw.githubusercontent.com/jagrusy/encore/main/scripts/bootstrap-sp3.sh | sudo bash
```

Once bootstrapped, open `/opt/encore` directly via Antigravity Remote Control (`agy`) to manage the hub without exposing inbound SSH or automated Git pulls.

### Manual Setup

1. Copy the sample inventory and configure your IPs, MAC addresses, and RTSP URLs:
   ```bash
   cp config/devices.example.yaml config/devices.yaml
   ```
2. Tune your Linux Surface Pro 3 and start the Hub stack:
   ```bash
   ./encore hub tune-sp3
   ./encore hub up
   ```
3. Check node and container status:
   ```bash
   ./encore status
   ```

See [docs/PLAYBOOK.md](docs/PLAYBOOK.md) for the step-by-step unlocking and pairing guide.
