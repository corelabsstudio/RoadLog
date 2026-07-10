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

RUN mkdir -p /app/data \
    && python -c "import server; print('import_ok', server.app.title)"

EXPOSE 8000

# Shell form so $PORT expands. Avoid start.sh CRLF issues on Windows git.
# Railway sets PORT (e.g. 8080).
CMD sh -c 'P="${PORT:-8000}"; if [ -z "$P" ]; then P=8000; fi; echo "[RoadLog] listen 0.0.0.0:$P"; exec python -m uvicorn server:app --host 0.0.0.0 --port "$P" --proxy-headers --forwarded-allow-ips="*"'
