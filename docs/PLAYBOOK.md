# Project Encore — Deployment Playbook

Follow these four phases in order to bring your entire hardware mesh online with zero soldering.

---

## Phase 1: Surface Pro 3 Hub Setup

### Fast Path (Recommended): One-Line Bootstrap (UFW LAN Lockdown + Antigravity Remote Control)

Run this once on your Linux Surface Pro 3, then follow any Tailscale login prompt it prints:

```bash
curl -fsSL https://raw.githubusercontent.com/jagrusy/encore/main/scripts/bootstrap-sp3.sh | sudo bash
```

This configures `sudo`, installs Docker + BlueZ + PipeWire/WirePlumber (`a2dp_source` mode) + Intel VA-API + ADB/Fastboot + UFW, disables lid-close suspend, clones `jagrusy/encore` to `/opt/encore`, starts the hardened Hub Docker stack, locks inbound host traffic via UFW to your local LAN, and installs Antigravity CLI (`agy`) so you can manage `/opt/encore` via Antigravity Remote Control.

### Manual Path

1. On your Linux Surface Pro 3, clone this repository and copy `config/devices.example.yaml` to `config/devices.yaml`.
2. Prepare the host for 24/7 headless operation (disables suspend on lid close, installs BlueZ/PipeWire and Intel VA-API drivers):
   ```bash
   ./encore hub tune-sp3
   ```
3. Edit `hub/cameras/go2rtc.yaml` with your RTSP camera URLs, then launch the Docker stack:
   ```bash
   ./encore hub up
   ```
4. Verify your **Kitchen Nest Hub** and any Google Cast speaker groups now appear in your iPhone/Mac AirPlay menu (via `encore-airconnect`) and in Music Assistant (`http://<sp3-ip>:8095`).
5. Pair your cameras in the Apple Home app using the PINs in `hub/cameras/go2rtc.yaml`.

---

## Phase 2: Unlock & Provision Echo Dot 2nd Gen (`biscuit`)

> **Important:** Do **not** connect a stock 2nd-Gen Echo Dot to Wi-Fi before unlocking it, or Amazon may push an updated firmware that blocks the exploit.

1. Connect the 2nd-Gen Echo Dot to your computer over Micro-USB and run:
   ```bash
   ./encore node unlock-dot2 living-room-dot
   ```
2. Complete initial Wi-Fi setup on the rooted Dot (firebreak blocks Amazon's OTA update hosts).
3. Deploy our vendored `overdub` + Encore webhook over ADB:
   ```bash
   ./nodes/echo-dot-gen2/provision.sh living-room-dot <surface-pro-3-ip>
   ```
4. In Music Assistant, add the Sendspin player using the pairing token printed by `provision.sh`.

---

## Phase 3: Unlock & Provision Echo Show 5 1st Gen (`checkers`)

Confirm the Echo Show 5 has **3 ports on the back** (Power, Micro-USB, and 3.5mm Aux).

1. Power off the Echo Show 5 and unplug its power cable.
2. Run the interactive guide:
   ```bash
   ./encore node unlock-show5
   ```
3. Follow the `amonet-checkers` steps (`bootrom-step.sh` while holding **Mute + Vol- + Vol+**, then `fastboot-step.sh`) to install TWRP.
4. Flash **LineageOS 18.1 (`checkers`)** in TWRP, boot into Android, and enable **USB Debugging (ADB)**.
5. Provision the Encore Show 5 Kiosk dashboard:
   ```bash
   ./nodes/echo-show5-gen1/show-agent/provision-show5.sh office-show5 <surface-pro-3-ip>
   ```
6. Repeat for your second Echo Show 5 (`bedroom-show5`).

---

## Phase 4: Pair Locked 3rd-Gen Dots & 2nd-Gen Standard Echo (Zero-Solder Satellites)

1. Put each 3rd-Gen Echo Dot (`donut`) or 2nd-Gen Standard Echo (`radar`) into Bluetooth pairing mode and pair it to its nearest Smart Node (`surface-pro-3`, `living-room-dot2`, `office-show5`, or `bedroom-show5`).
2. Add their Bluetooth MAC addresses to `config/devices.yaml` under `bluetooth_satellites`.
3. For satellites paired directly to the Surface Pro 3, run:
   ```bash
   ./encore bt sync
   ```
   `bt-multi-sink` will keep their Bluetooth A2DP links alive and expose each speaker as an individual AirPlay target.
4. Press the physical **Microphone Mute** button on every satellite Echo and block their MAC addresses from internet access in your router settings.
