"""Project Encore Brain — Mesh Orchestrator for Surface Pro 3, Echo Show 5s, and Echo Dots."""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import time
from typing import Any

import httpx
import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

CONFIG_PATH = pathlib.Path(os.environ.get("ENCORE_CONFIG", "/app/config/devices.yaml"))
GO2RTC_URL = os.environ.get("GO2RTC_URL", "http://127.0.0.1:1984")
AI_AGENT_ENDPOINT = os.environ.get("AI_AGENT_ENDPOINT", "http://127.0.0.1:8080/v1/chat/completions")
UI_DIR = pathlib.Path(__file__).resolve().parent / "ui"

app = FastAPI(title="Project Encore Brain", version="0.1.0")


class CameraAlertRequest(BaseModel):
    camera_id: str = Field(..., description="Camera stream ID defined in go2rtc.yaml")
    reason: str = Field(default="motion", description="Trigger reason (motion, doorbell, person)")
    duration_sec: int = Field(default=30, ge=5, le=300)
    target_nodes: list[str] | None = Field(default=None, description="Specific Show 5 node IDs, or all if omitted")


class AIWakeRequest(BaseModel):
    source_node: str = Field(..., description="Node ID that triggered the wake (e.g. living-room-dot2)")
    event: str = Field(default="action_button", description="Trigger event type")
    prompt: str | None = Field(default=None, description="Optional text/transcript to forward to the AI agent")


class NodeConnectionManager:
    """Tracks active WebSocket connections from Echo Show 5 kiosk displays."""

    def __init__(self) -> None:
        self._nodes: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def register(self, node_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._nodes[node_id] = ws

    async def unregister(self, node_id: str) -> None:
        async with self._lock:
            self._nodes.pop(node_id, None)

    async def broadcast(self, payload: dict[str, Any], target_nodes: list[str] | None = None) -> list[str]:
        delivered: list[str] = []
        dead: list[str] = []
        async with self._lock:
            targets = list(self._nodes.items())
        for node_id, ws in targets:
            if target_nodes and node_id not in target_nodes:
                continue
            try:
                await ws.send_text(json.dumps(payload))
                delivered.append(node_id)
            except Exception:
                dead.append(node_id)
        for node_id in dead:
            await self.unregister(node_id)
        return delivered

    async def connected_ids(self) -> list[str]:
        async with self._lock:
            return sorted(self._nodes.keys())


manager = NodeConnectionManager()
LAST_EVENTS: list[dict[str, Any]] = []


def load_devices_config() -> dict[str, Any]:
    if not CONFIG_PATH.is_file():
        return {}
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def record_event(event: dict[str, Any]) -> None:
    LAST_EVENTS.append(event)
    if len(LAST_EVENTS) > 50:
        del LAST_EVENTS[0]


if UI_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "encore-brain"}


@app.get("/api/v1/mesh/state")
async def mesh_state() -> dict[str, Any]:
    cfg = load_devices_config()
    return {
        "timestamp": time.time(),
        "hub": cfg.get("hub", {}),
        "cast_devices": cfg.get("cast_devices", []),
        "smart_nodes": cfg.get("smart_nodes", []),
        "bluetooth_satellites": cfg.get("bluetooth_satellites", []),
        "cameras": cfg.get("cameras", []),
        "connected_displays": await manager.connected_ids(),
        "recent_events": LAST_EVENTS[-10:],
    }


@app.post("/api/v1/camera/alert")
async def camera_alert(req: CameraAlertRequest) -> dict[str, Any]:
    event = {
        "type": "camera_alert",
        "camera_id": req.camera_id,
        "reason": req.reason,
        "duration_sec": req.duration_sec,
        "webrtc_url": f"{GO2RTC_URL}/stream.html?src={req.camera_id}&mode=webrtc",
        "snapshot_url": f"{GO2RTC_URL}/api/frame.jpeg?src={req.camera_id}",
        "timestamp": time.time(),
    }
    record_event(event)
    delivered = await manager.broadcast(event, target_nodes=req.target_nodes)
    return {"status": "broadcasted", "delivered_to": delivered, "event": event}


@app.post("/api/v1/ai/wake")
async def ai_wake(req: AIWakeRequest) -> dict[str, Any]:
    cfg = load_devices_config()
    agent_cfg = (cfg.get("hub") or {}).get("ai_agent") or {}
    endpoint = agent_cfg.get("endpoint") or AI_AGENT_ENDPOINT
    model = agent_cfg.get("model") or "local-assistant"

    reply_text = f"Wake received from {req.source_node} ({req.event}). Ready for command."
    if req.prompt:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    endpoint,
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": req.prompt}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                reply_text = data["choices"][0]["message"]["content"]
        except Exception as exc:
            reply_text = f"AI endpoint unavailable ({exc}); local prompt noted: {req.prompt}"

    event = {
        "type": "ai_card",
        "source_node": req.source_node,
        "event": req.event,
        "prompt": req.prompt,
        "reply": reply_text,
        "timestamp": time.time(),
    }
    record_event(event)
    delivered = await manager.broadcast(event)
    return {"status": "ok", "reply": reply_text, "delivered_to": delivered}


@app.websocket("/ws/node/{node_id}")
async def node_websocket(websocket: WebSocket, node_id: str) -> None:
    await manager.register(node_id, websocket)
    try:
        await websocket.send_text(json.dumps({"type": "welcome", "node_id": node_id, "go2rtc_url": GO2RTC_URL}))
        while True:
            raw = await websocket.receive_text()
            if raw == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "timestamp": time.time()}))
    except WebSocketDisconnect:
        await manager.unregister(node_id)
    except Exception:
        await manager.unregister(node_id)


@app.get("/")
async def root() -> dict[str, Any]:
    index_file = UI_DIR / "show5.html"
    return {
        "name": "Project Encore Brain",
        "docs": "/docs",
        "show5_ui": "/ui/show5.html" if index_file.is_file() else "mount ../nodes/echo-show5-gen1/show-agent for UI",
    }
