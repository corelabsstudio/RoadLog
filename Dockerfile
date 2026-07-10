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
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.prod.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements.prod.txt

COPY modules ./modules
COPY web ./web
COPY server.py ./
COPY start.sh ./
COPY supabase_schema.sql ./

RUN mkdir -p /app/data \
    && chmod +x /app/start.sh \
    && python -c "import server; print('import_ok', server.app.title)"

EXPOSE 8000

# Healthcheck inside container (optional; Railway UI healthcheck can be disabled)
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/healthz" || exit 1

CMD ["/app/start.sh"]
