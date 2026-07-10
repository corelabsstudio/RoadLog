#!/bin/sh
# Railway / container entrypoint
set -eu

PORT_VALUE="${PORT:-8000}"
# empty string PORT (some platforms) → fallback
if [ -z "$PORT_VALUE" ]; then
  PORT_VALUE=8000
fi

echo "[RoadLog] starting uvicorn host=0.0.0.0 port=${PORT_VALUE}"
echo "[RoadLog] APP_ENV=${APP_ENV:-unset}"

exec python -m uvicorn server:app \
  --host 0.0.0.0 \
  --port "$PORT_VALUE" \
  --proxy-headers \
  --forwarded-allow-ips='*'
