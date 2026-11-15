FROM python:3.12-slim

WORKDIR /app

COPY hub/encore-brain/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY hub/encore-brain/main.py /app/main.py
COPY nodes/echo-show5-gen1/show-agent/index.html /app/ui/show5.html
COPY nodes/echo-show5-gen1/show-agent/app.js /app/ui/app.js

ENV ENCORE_CONFIG=/app/config/devices.yaml
ENV BRAIN_PORT=8765

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${BRAIN_PORT}"]
