(function () {
  const params = new URLSearchParams(window.location.search);
  const nodeId = params.get("node") || "echo-show5-1";

  const clockEl = document.getElementById("clock");
  const dateEl = document.getElementById("date");
  const dotEl = document.getElementById("conn-dot");
  const labelEl = document.getElementById("conn-label");
  const aiReplyEl = document.getElementById("ai-reply");
  const overlayEl = document.getElementById("camera-overlay");
  const camTitleEl = document.getElementById("cam-title");
  const camFrameEl = document.getElementById("cam-frame");

  let hideTimer = null;

  function updateClock() {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    dateEl.textContent = now.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });
  }
  updateClock();
  setInterval(updateClock, 1000);

  function showCamera(title, url, durationSec) {
    if (hideTimer) clearTimeout(hideTimer);
    camTitleEl.textContent = title;
    camFrameEl.src = url;
    overlayEl.classList.add("active");
    hideTimer = setTimeout(dismissCamera, (durationSec || 30) * 1000);
  }

  function dismissCamera() {
    overlayEl.classList.remove("active");
    camFrameEl.src = "about:blank";
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
  }

  document.getElementById("close-cam").addEventListener("click", dismissCamera);

  document.getElementById("wake-btn").addEventListener("click", async () => {
    aiReplyEl.textContent = "Contacting Surface Pro 3 AI Agent...";
    try {
      const resp = await fetch("/api/v1/ai/wake", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_node: nodeId,
          event: "screen_tap",
          prompt: "Give a brief 1-sentence home mesh status greeting.",
        }),
      });
      const data = await resp.json();
      aiReplyEl.textContent = data.reply || "Ready.";
    } catch (err) {
      aiReplyEl.textContent = "Failed to reach Encore Brain: " + err;
    }
  });

  document.getElementById("cam-btn").addEventListener("click", async () => {
    await fetch("/api/v1/camera/alert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        camera_id: "front_door",
        reason: "manual_view",
        duration_sec: 30,
        target_nodes: [nodeId],
      }),
    });
  });

  function connectWS() {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/node/${encodeURIComponent(nodeId)}`);

    ws.onopen = () => {
      dotEl.classList.add("online");
      labelEl.textContent = `Connected (${nodeId})`;
    };

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data);
      if (msg.type === "camera_alert") {
        showCamera(`${msg.camera_id} (${msg.reason})`, msg.webrtc_url, msg.duration_sec);
      } else if (msg.type === "ai_card") {
        aiReplyEl.textContent = msg.reply || "";
      }
    };

    ws.onclose = () => {
      dotEl.classList.remove("online");
      labelEl.textContent = "Reconnecting to Encore Brain...";
      setTimeout(connectWS, 3000);
    };
  }

  connectWS();
})();
