#!/usr/bin/env python3
"""Manage persistent Bluetooth A2DP connections and per-device Shairport-Sync instances."""

from __future__ import annotations

import argparse
import logging
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [bt-multi-sink] %(levelname)s %(message)s",
)
log = logging.getLogger("bt-multi-sink")

A2DP_SINK_UUID = "0000110b-0000-1000-8000-00805f9b34fb"


def load_yaml(path: pathlib.Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        return _fallback_parse_satellites(path.read_text(encoding="utf-8"))


def _fallback_parse_satellites(text: str) -> dict[str, Any]:
    satellites: list[dict[str, str]] = []
    in_section = False
    cur: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            if cur:
                satellites.append(cur)
                cur = {}
            in_section = line[:-1].strip() == "bluetooth_satellites"
            continue
        if not in_section:
            continue
        stripped = line.lstrip()
        if stripped.startswith("- "):
            if cur:
                satellites.append(cur)
                cur = {}
            stripped = stripped[2:]
        if ":" in stripped:
            k, v = stripped.split(":", 1)
            cur[k.strip()] = v.strip().strip('"').strip("'")
    if cur:
        satellites.append(cur)
    return {"bluetooth_satellites": satellites}


def _run_cmd(cmd: list[str], timeout: float = 12.0) -> subprocess.CompletedProcess[str] | None:
    """Run a subprocess with a hard timeout so bluetoothctl cannot hang."""
    try:
        return subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        log.warning("Command timed out after %.1fs: %s", timeout, " ".join(cmd))
        return None


def _bt_info(mac: str) -> tuple[bool, bool, bool]:
    """Return (connected, known_in_bluez, paired_or_bonded)."""
    proc = _run_cmd(["bluetoothctl", "info", mac], timeout=8.0)
    if proc is None:
        return False, False, False
    out = proc.stdout + proc.stderr
    if "not available" in out:
        return False, False, False
    connected = "Connected: yes" in out
    paired_or_bonded = ("Paired: yes" in out) or ("Bonded: yes" in out)
    return connected, True, paired_or_bonded


def is_bt_connected(mac: str) -> tuple[bool, bool]:
    """Return (connected, known_in_bluez)."""
    connected, known, _ = _bt_info(mac)
    return connected, known


def ensure_bt_connected(mac: str, pair: bool = False) -> bool:
    connected, known, paired_or_bonded = _bt_info(mac)
    if connected:
        return True
    needs_pair = pair or not paired_or_bonded
    scan_proc = None
    try:
        if needs_pair or not known:
            log.info("Scanning for %s before pairing/connecting...", mac)
            scan_proc = subprocess.Popen(
                ["bluetoothctl", "scan", "on"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(8):
                time.sleep(1)
                _, known, _ = _bt_info(mac)
                if known:
                    break
        if needs_pair:
            _run_cmd(["bluetoothctl", "pair", mac], timeout=12.0)
        _run_cmd(["bluetoothctl", "trust", mac], timeout=8.0)
        _run_cmd(["bluetoothctl", "connect", mac], timeout=12.0)
    finally:
        if scan_proc is not None and scan_proc.poll() is None:
            scan_proc.terminate()
            try:
                scan_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                scan_proc.kill()
    connected, _ = is_bt_connected(mac)
    if not connected:
        log.warning("Failed to connect Bluetooth A2DP target %s", mac)
    return connected


def _query_pulse_sink(underscored_mac: str) -> str | None:
    proc = _run_cmd(["pactl", "list", "short", "sinks"], timeout=8.0)
    if proc is None or proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and underscored_mac in parts[1].upper():
            return parts[1]
    return None


def pulse_sink_for_mac(mac: str) -> str | None:
    """Resolve the PipeWire/PulseAudio bluez sink name for a connected MAC."""
    underscored = mac.upper().replace(":", "_")
    sink = _query_pulse_sink(underscored)
    if sink:
        return sink
    card_name = f"bluez_card.{underscored}"
    _run_cmd(["pactl", "set-card-profile", card_name, "a2dp-sink"], timeout=8.0)
    _run_cmd(["bluetoothctl", "connect", mac, A2DP_SINK_UUID], timeout=10.0)
    time.sleep(1)
    return _query_pulse_sink(underscored)


def spawn_shairport(sat: dict[str, Any], sink_name: str, cfg_dir: pathlib.Path) -> subprocess.Popen[str]:
    sat_id = sat["id"]
    airplay_name = sat.get("airplay_name") or sat_id
    port = int(sat.get("airplay_port", 5100))
    conf_path = cfg_dir / f"shairport-{sat_id}.conf"
    conf_path.write_text(
        f"""general = {{
  name = "{airplay_name}";
  port = {port};
}};
pa = {{
  sink = "{sink_name}";
}};
""",
        encoding="utf-8",
    )
    log.info("Starting shairport-sync for %s (%s) -> sink %s on port %d", sat_id, airplay_name, sink_name, port)
    return subprocess.Popen(
        ["shairport-sync", "-o", "pa", "-c", str(conf_path)],
        text=True,
        env={**os.environ, "PULSE_SINK": sink_name},
    )


def get_hub_satellites(config: dict[str, Any]) -> list[dict[str, Any]]:
    hub_name = (config.get("hub") or {}).get("name", "surface-pro-3")
    satellites = config.get("bluetooth_satellites") or []
    return [
        sat
        for sat in satellites
        if sat.get("host_node") in (hub_name, "surface-pro-3")
        and sat.get("bt_mac")
        and not str(sat.get("bt_mac")).upper().startswith("AA:BB:CC:DD:EE:")
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Encore Bluetooth Multi-Sink Manager")
    parser.add_argument("--config", required=True, help="Path to devices.yaml")
    parser.add_argument("--pair-once", action="store_true", help="Pair/connect all hub satellites and exit")
    parser.add_argument("--poll-seconds", type=int, default=15, help="Watchdog poll interval")
    args = parser.parse_args()

    cfg_path = pathlib.Path(args.config)
    if not cfg_path.is_file():
        log.error("Config file not found: %s", cfg_path)
        return 1

    config = load_yaml(cfg_path)
    satellites = get_hub_satellites(config)
    if not satellites:
        log.info("No bluetooth_satellites assigned to surface-pro-3 in %s", cfg_path)
        if args.pair_once:
            return 0

    if args.pair_once:
        for sat in satellites:
            ensure_bt_connected(sat["bt_mac"], pair=True)
        return 0

    running: dict[str, subprocess.Popen[str]] = {}
    stop_requested = False

    def handle_sig(_signum: int, _frame: Any) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT, handle_sig)

    with tempfile.TemporaryDirectory(prefix="encore-shairport-") as tmpdir:
        tmp_path = pathlib.Path(tmpdir)
        while not stop_requested:
            config = load_yaml(cfg_path)
            satellites = get_hub_satellites(config)
            for sat in satellites:
                sat_id = sat["id"]
                mac = sat["bt_mac"]
                if not ensure_bt_connected(mac, pair=False):
                    continue
                sink = pulse_sink_for_mac(mac)
                if not sink:
                    log.warning("Bluetooth %s connected, waiting for Pulse/PipeWire A2DP sink...", mac)
                    continue
                proc = running.get(sat_id)
                if proc is None or proc.poll() is not None:
                    running[sat_id] = spawn_shairport(sat, sink, tmp_path)
            time.sleep(args.poll_seconds)

        for proc in running.values():
            if proc.poll() is None:
                proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
