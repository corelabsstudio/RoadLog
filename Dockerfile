# Railway production — FastAPI + web SPA
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.prod.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements.prod.txt

COPY modules ./modules
COPY web ./web
COPY server.py ./
COPY supabase_schema.sql ./

# Entrypoint written inside image (always LF, expands $PORT at runtime)
RUN mkdir -p /app/data \
    && printf '%s\n' \
        '#!/bin/sh' \
        'set -eu' \
        'P="${PORT:-8080}"' \
        'if [ -z "$P" ]; then P=8080; fi' \
        'echo "[RoadLog] starting 0.0.0.0:${P} APP_ENV=${APP_ENV:-unset}"' \
        'exec python -m uvicorn server:app --host 0.0.0.0 --port "${P}" --proxy-headers --forwarded-allow-ips="*"' \
        > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh \
    && python -c "import server; print('import_ok', server.app.title)"

EXPOSE 8080

CMD ["/app/entrypoint.sh"]
