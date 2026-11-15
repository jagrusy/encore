#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${ENCORE_REPO_URL:-https://github.com/jagrusy/encore.git}"
ENCORE_DIR="${ENCORE_DIR:-/opt/encore}"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This bootstrap script must be run on your Linux Surface Pro 3." >&2
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Please run as root (e.g. curl -fsSL ... | sudo bash)." >&2
  exit 1
fi

TARGET_USER="${SUDO_USER:-$(awk -F: '$3>=1000 && $3<60000 {print $1; exit}' /etc/passwd)}"
if [[ -z "$TARGET_USER" ]]; then
  TARGET_USER="root"
fi

echo "=== Project Encore: Surface Pro 3 Bootstrap ==="
echo "Target user: $TARGET_USER"
echo "Install dir: $ENCORE_DIR"

echo "1. Configuring passwordless sudo for $TARGET_USER..."
if [[ "$TARGET_USER" != "root" ]]; then
  echo "$TARGET_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-encore-nopasswd
  chmod 0440 /etc/sudoers.d/90-encore-nopasswd
fi

echo "2. Installing system packages (BlueZ, PipeWire, Intel VA-API, ADB/Fastboot, UFW)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  curl \
  git \
  ca-certificates \
  ufw \
  avahi-daemon \
  bluez \
  pipewire \
  pipewire-audio \
  wireplumber \
  libspa-0.2-bluetooth \
  vainfo \
  intel-media-va-driver \
  adb \
  fastboot \
  libusb-1.0-0 \
  python3 \
  python3-yaml

systemctl enable --now avahi-daemon || true

echo "3. Configuring 24/7 power & lid rules + WirePlumber A2DP source role + Echo USB udev rules..."
mkdir -p /etc/wireplumber/bluetooth.lua.d
cat > /etc/wireplumber/bluetooth.lua.d/51-encore-bt.lua <<'EOF'
bluez_monitor.properties["bluez5.roles"] = "[ a2dp_source ]"
bluez_monitor.properties["with-logind"] = false
EOF
if [[ "$TARGET_USER" != "root" ]]; then
  TARGET_UID="$(id -u "$TARGET_USER")"
  su - "$TARGET_USER" -c "XDG_RUNTIME_DIR=/run/user/$TARGET_UID systemctl --user restart wireplumber" || true
fi
mkdir -p /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/99-encore-always-on.conf <<'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
IdleAction=ignore
EOF
systemctl restart systemd-logind || true

groupadd -f plugdev
cat > /etc/udev/rules.d/51-echo-dot.rules <<'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="1949", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", ATTR{idProduct}=="4ee2", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", ATTR{idProduct}=="d001", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="0bb4", ATTR{idProduct}=="0c01", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="0e8d", ATTR{idProduct}=="0003", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="0e8d", ATTR{idProduct}=="201c", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="tty", ATTRS{idVendor}=="0e8d", ATTRS{idProduct}=="0003", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1949", ATTRS{idProduct}=="2007", MODE="0660", GROUP="plugdev", TAG+="uaccess"
EOF
udevadm control --reload || true
udevadm trigger || true

echo "4. Installing Docker Engine & Compose plugin..."
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

if [[ "$TARGET_USER" != "root" ]]; then
  for grp in docker plugdev video render; do
    if getent group "$grp" >/dev/null 2>&1; then
      usermod -aG "$grp" "$TARGET_USER" || true
    fi
  done
fi

echo "5. Cloning Project Encore to $ENCORE_DIR..."
if [[ -d "$ENCORE_DIR/.git" ]]; then
  git -C "$ENCORE_DIR" fetch origin main
  git -C "$ENCORE_DIR" pull --ff-only origin main
else
  git clone "$REPO_URL" "$ENCORE_DIR"
fi
git config --global --add safe.directory "$ENCORE_DIR" || true
git config --system --add safe.directory "$ENCORE_DIR" || true

if [[ ! -f "$ENCORE_DIR/config/devices.yaml" && -f "$ENCORE_DIR/config/devices.example.yaml" ]]; then
  cp "$ENCORE_DIR/config/devices.example.yaml" "$ENCORE_DIR/config/devices.yaml"
fi
if [[ ! -f "$ENCORE_DIR/hub/.env" && -f "$ENCORE_DIR/hub/.env.example" ]]; then
  cp "$ENCORE_DIR/hub/.env.example" "$ENCORE_DIR/hub/.env"
fi

if [[ "$TARGET_USER" != "root" ]]; then
  chown -R "$TARGET_USER:$TARGET_USER" "$ENCORE_DIR"
fi

echo "6. Starting Hub Docker stack..."
"$ENCORE_DIR/encore" hub up

echo "7. Configuring UFW firewall (LAN + Docker only, default deny incoming)..."
LAN_CIDR="${ENCORE_LAN_CIDR:-$(ip -o -f inet route show dev "$(ip route show default | awk 'NR==1{print $5}')" proto kernel scope link 2>/dev/null | awk 'NR==1{print $1}')}"
if [[ -z "$LAN_CIDR" ]]; then
  LAN_CIDR="192.168.0.0/16"
fi
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow from "$LAN_CIDR"
ufw allow from 172.16.0.0/12
ufw --force enable

echo "8. Installing Google Antigravity CLI (agy) for $TARGET_USER..."
if [[ "$TARGET_USER" != "root" ]]; then
  su - "$TARGET_USER" -c 'curl -fsSL https://antigravity.google/cli/install.sh | bash' || true
  USER_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
  if [[ -x "$USER_HOME/.local/bin/agy" ]]; then
    ln -sf "$USER_HOME/.local/bin/agy" /usr/local/bin/agy
  fi
else
  curl -fsSL https://antigravity.google/cli/install.sh | bash || true
  if [[ -x "/root/.local/bin/agy" ]]; then
    ln -sf "/root/.local/bin/agy" /usr/local/bin/agy
  fi
fi

echo "9. Installing Tailscale..."
if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
systemctl enable --now tailscaled

echo ""
echo "==================================================================="
echo "Almost done! Approve the Tailscale login URL below to finish."
echo "Once approved, this Surface Pro 3 will:"
echo "  - Be reachable on your Tailnet as 'encore-sp3'"
echo "  - Restrict inbound host firewall traffic to your local LAN"
echo "  - Have Antigravity CLI ('agy') ready — run: cd /opt/encore && agy"
echo "==================================================================="
echo ""
tailscale up --hostname=encore-sp3
