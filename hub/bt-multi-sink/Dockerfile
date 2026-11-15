FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bluez \
    pulseaudio-utils \
    shairport-sync \
    python3 \
    python3-yaml \
    avahi-daemon \
    dbus \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY bt_sink_manager.py /app/bt_sink_manager.py

ENTRYPOINT ["python3", "/app/bt_sink_manager.py"]
CMD ["--config", "/app/config/devices.yaml"]
