# Project Encore — Surface Pro 3 Hub Handoff

**Repository:** `https://github.com/jagrusy/encore`  
**Hub Workspace Path:** `/opt/encore` on `grusy-Surface-Pro-3`  
**Live Local Inventory (gitignored):** `/opt/encore/config/devices.yaml` *(contains the live Surface LAN IP, Cast targets, and Bluetooth MAC addresses — never commit this file)*  
**Context:** Initial architecture, repository setup, Surface Pro 3 Linux configuration, Docker hub deployment, WirePlumber Bluetooth fixes, and security hardening were completed from the user's Mac. Going forward, all new agent sessions run directly on `grusy-Surface-Pro-3` inside `/opt/encore` via Antigravity Remote Control.

---

## 1. Mission & Architecture Overview

**Project Encore** repurposes retired smart-home hardware into a unified, local-first mesh for **multi-room audio** (Google Cast, AirPlay, Sendspin), **low-latency HomeKit/WebRTC cameras**, and **voice/display AI orchestration**:

- **Central Hub (`grusy-Surface-Pro-3`):** Runs the Docker Compose stack (`/opt/encore/hub/docker-compose.yml`), Bluetooth A2DP multi-sink bridge, PipeWire/WirePlumber audio routing, and `udev` / USB flashing tools for locked Echo hardware. *(Note: a PS3 Slim was ruled out due to its 256 MB RAM ceiling, big-endian `ppc64` constraints, and ~85W+ idle power draw.)*
- **Existing LAN Google Cast Targets:** Discovered automatically on the LAN and bridged to AirPlay via AirConnect (`encore-airconnect`), and grouped natively inside Music Assistant (`encore-music-assistant`). Check `/opt/encore/config/devices.yaml` for the user's configured Cast targets.
- **USB-Unlockable Echos (No-Solder):** Rooted/flashed directly over Micro-USB from the Surface Pro 3 (`biscuit` Echo Dot 2nd Gen via `firebreak` + `overdub`; `checkers` Echo Show 5 1st Gen via `amonet-checkers` + LineageOS 18.1 + `show-agent`).
- **Locked Bluetooth Satellite Echos (No-Solder):** Echo Dot 3rd Gen (`donut`) and Echo 2nd Gen (`radar`) speakers paired as A2DP speaker sinks to the Surface Pro 3 (or to unlocked nodes) and exposed individually over AirPlay via `shairport-sync`.

---

## 2. Host Environment & Security Posture (`grusy-Surface-Pro-3`)

- **Hardware & OS:** Surface Pro 3 (`x86_64`, 8 GB RAM, 256 GB SSD, Linux, Intel QuickSync `/dev/dri/renderD128`), primary user `grusy` (UID `1000`). Check `/opt/encore/config/devices.yaml` (gitignored) or `ip -brief addr` / `bluetoothctl list` locally for the hub's current LAN IP and Bluetooth MAC.
- **Hardened Access & Host Configuration:**
  - **Direct Remote Control Only (No Auto-Pull / No Inbound SSH):** GitHub auto-pull (`encore-autodeploy.timer`) and the bootstrap SSH server/authorized keys were removed. Antigravity Remote Control (`agy`) communicates outbound and binds only to `127.0.0.1`, eliminating remote root execution via GitHub pushes or inbound LAN port `22`.
  - **Host Firewall (`ufw`):** Enabled with `default deny incoming` and `default allow outgoing`, allowing inbound traffic only from the home LAN subnet and local Docker networks (`172.16.0.0/12`).
  - **Workspace Ownership:** `/opt/encore` is owned by `grusy:grusy`.
  - **24/7 Lid-Closed Power Policy:** `/etc/systemd/logind.conf.d/99-encore-always-on.conf` ignores lid-close and idle suspend.
  - **MediaTek / Amazon USB Rules:** `/etc/udev/rules.d/51-echo-dot.rules` grants `plugdev` access to MediaTek BootROM (`0e8d:0003`, `0e8d:201c`), fastboot, ADB, and Amazon USB IDs.
  - **WirePlumber Bluetooth Role Fix:** `/etc/wireplumber/bluetooth.lua.d/51-encore-bt.lua` sets:
    ```lua
    bluez_monitor.properties["bluez5.roles"] = "[ a2dp_source ]"
    bluez_monitor.properties["with-logind"] = false
    ```
    **Why this matters:** Amazon Echos advertise *both* `Audio Source (0000110a)` and `Audio Sink (0000110b)`. With WirePlumber's default roles enabled, `bluetoothd` registered local `/MediaEndpoint/A2DPSink/*` endpoints and connected an Echo backwards as an `audio-gateway` input (`bluez_input.*`). Restricting WirePlumber to `[ a2dp_source ]` ensures `bluetoothd` only registers `/MediaEndpoint/A2DPSource/*` so Echos connect cleanly as A2DP output speaker sinks (`bluez_output.*`). Also persisted in [scripts/bootstrap-sp3.sh](../scripts/bootstrap-sp3.sh).
  - **mDNS / AirPlay Discovery:** `avahi-daemon` is installed and active on the host.

---

## 3. Running Hub Services (`/opt/encore/hub/docker-compose.yml`)

All five containers run with `network_mode: host`, `restart: unless-stopped`, and `security_opt: [no-new-privileges:true]`:

| Container | Ports / URL | Purpose & State |
| :--- | :--- | :--- |
| `encore-music-assistant` | `http://<hub-ip>:8095` | Music Assistant server (Google Cast + AirPlay + Sendspin + music providers). |
| `encore-airconnect` | mDNS AirPlay bridges | Runs extracted static `aircast-linux-x86_64-static`, discovering Google Cast devices and speaker groups on the LAN and exposing them as AirPlay targets. |
| `encore-go2rtc` | `:1984` UI/API, `:8554` RTSP, `:8555` WebRTC | Non-privileged hardware-accelerated (`/dev/dri`) RTSP/WebRTC/HomeKit camera bridge configured in [hub/cameras/go2rtc.yaml](../hub/cameras/go2rtc.yaml) (no CORS `origin: "*"` wildcard). |
| `encore-brain` | `http://<hub-ip>:8765` | FastAPI orchestrator ([hub/encore-brain/main.py](../hub/encore-brain/main.py)): serves Show 5 kiosk UI (`/ui/show5.html`), WebSocket push (`/ws/node/{node_id}`), camera popup alerts (`POST /api/v1/camera/alert`), and AI wake webhook (`POST /api/v1/ai/wake` -> `AI_AGENT_ENDPOINT`, default `http://127.0.0.1:8080/v1/chat/completions`). |
| `encore-bt-multi-sink` | AirPlay ports `5101+` | Runs [hub/bt-multi-sink/bt_sink_manager.py](../hub/bt-multi-sink/bt_sink_manager.py) against host D-Bus (`/var/run/dbus`) and `grusy`'s PipeWire-Pulse socket (`unix:/run/user/1000/pulse/native`) to keep configured Bluetooth satellites connected and spawn one `shairport-sync -o pa` AirPlay target per speaker. |

---

## 4. Vendored Upstream Projects ([UPSTREAM.lock.json](../UPSTREAM.lock.json))

All five upstreams are vendored directly inside the monorepo (check upstream updates anytime via `./encore sync-upstreams`):

| Project | Repo Path | Upstream |
| :--- | :--- | :--- |
| `firebreak` | [nodes/echo-dot-gen2/firebreak](../nodes/echo-dot-gen2/firebreak) | `bboe/firebreak` (`307905d0e954`) — USB unlock for Echo Dot 2nd Gen (`biscuit`) |
| `overdub` | [nodes/echo-dot-gen2/overdub](../nodes/echo-dot-gen2/overdub) | `bboe/overdub` (`7dfeb1aba950`) — Drop-in firmware replacement for `biscuit` |
| `amonet-checkers` | [nodes/echo-show5-gen1/amonet-checkers](../nodes/echo-show5-gen1/amonet-checkers) | `R0rt1z2/amonet` branch `mt8163-echo-show` (`d6179b8a2ba4`) — BootROM unlock for Echo Show 5 1st Gen (`checkers`) |
| `aiosendspin` | [shared/aiosendspin](../shared/aiosendspin) | `Sendspin/aiosendspin` (`2174cdc4dd42`) — Synchronized Sendspin audio protocol library |
| `airconnect` | [hub/airconnect/upstream](../hub/airconnect/upstream) | `philippe44/AirConnect` (`e2758fde86b3`) — `aircast-linux-x86_64-static` binary |

---

## 5. Remaining Device Onboarding Tasks on `grusy-Surface-Pro-3`

First inspect `/opt/encore/config/devices.yaml` locally on the Surface Pro 3 to read the user's real hub IP, LAN Cast devices, and first Bluetooth Echo MAC.

1. **Finish Pairing the First Bluetooth Satellite Echo & Verify AirPlay Playback**
   - Read its `bt_mac` and `airplay_name` from `/opt/encore/config/devices.yaml` under `bluetooth_satellites`. (WirePlumber is already restricted to `a2dp_source`, and `bt_sink_manager.py` enforces hard subprocess timeouts so `bluetoothctl` never hangs.)
   - Ask the user to say **"Alexa, pair"** to put it back into pairing mode (its earlier pairing attempt left `Paired: no`, `Bonded: no`).
   - Run:
     ```bash
     cd /opt/encore
     ./encore bt sync
     ```
   - Verify PipeWire creates a `bluez_output.*` sink and `encore-bt-multi-sink` launches `shairport-sync`:
     ```bash
     bluetoothctl info <bt_mac>
     docker exec encore-bt-multi-sink pactl list short sinks
     docker logs --tail 30 encore-bt-multi-sink
     pgrep -fa shairport-sync
     ```
   - Repeat for the user's remaining Echo Dot 3rd Gen (`donut`) and Echo 2nd Gen (`radar`) speakers by adding entries under `bluetooth_satellites` in `/opt/encore/config/devices.yaml` with sequential `airplay_port` numbers (`5102`, `5103`, ...), muting their mics physically, and blocking their MACs from WAN on the router.

2. **Unlock & Provision the 1x Echo Dot 2nd Gen (`biscuit`, Micro-USB on back, No-Solder)**
   - Connect it via Micro-USB to `grusy-Surface-Pro-3` while holding the **Action (dot)** button (`0e8d:0003` MediaTek BootROM).
   - Run:
     ```bash
     cd /opt/encore
     ./encore node unlock-dot2 living-room-dot
     ```
   - After Wi-Fi setup + ADB access, run:
     ```bash
     /opt/encore/nodes/echo-dot-gen2/provision.sh living-room-dot <hub-ip>
     ```

3. **Unlock & Provision the 2x Echo Show 5 1st Gen (`checkers`, 3 ports on back, No-Solder)**
   - Follow `./encore node unlock-show5` (`bootrom-step.sh` in [nodes/echo-show5-gen1/amonet-checkers](../nodes/echo-show5-gen1/amonet-checkers) while holding Mute + Vol Down + Vol Up when plugging in Micro-USB + power -> `fastboot-step.sh` -> flash LineageOS 18.1 in TWRP -> enable ADB).
   - Run `/opt/encore/nodes/echo-show5-gen1/show-agent/provision-show5.sh <node-id> <hub-ip>` for each unit, pin `http://<hub-ip>:8765/ui/show5.html?node=<node-id>` in Fully Kiosk Browser, and configure Sendspin/AirPlay playback + optional Bluetooth relay.

4. **Configure Cameras, Music Assistant & AI Backend**
   - Replace the placeholder RTSP URLs in `/opt/encore/hub/cameras/go2rtc.yaml` and `/opt/encore/config/devices.yaml`, restart `go2rtc` + `encore-brain`, and pair cameras into Apple Home using the HomeKit PINs.
   - Configure Music Assistant (`http://<hub-ip>:8095`) music sources and multi-room speaker groups (Cast + AirPlay + Sendspin).
   - Point `hub.ai_agent.endpoint` in `/opt/encore/config/devices.yaml` (or `AI_AGENT_ENDPOINT` in `/opt/encore/hub/.env`) to a local/remote OpenAI-compatible AI endpoint so `encore-brain` voice/button triggers return live AI responses.

---

## 6. Repo Hygiene & Privacy Guardrails

- **Never Commit Local Inventory, Keys, or Hardware Identifiers:** `config/devices.yaml`, `hub/.env`, `hub/data/`, `hub/cameras/recordings/`, and `.ssh/` are gitignored. Never commit real home LAN IPs (`192.168.*`), router/device MAC addresses (Bluetooth/Wi-Fi BSSIDs), SSH keys, or personal device names to tracked files in this public repository.
- **Git Push Auth on `grusy-Surface-Pro-3`:** Check whether git credentials are configured in `/opt/encore` before pushing to `github.com/jagrusy/encore`, and remember the repository is public.
- **Quick Health Check Commands on Surface Pro 3:**
  ```bash
  cd /opt/encore
  ./encore status
  docker compose -f hub/docker-compose.yml ps
  sudo ufw status verbose
  ```
