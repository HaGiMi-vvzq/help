# ---- Python backend ----
FROM python:3.12-slim AS backend

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Create required directories
RUN mkdir -p /app/logs /app/uploads /app/db_backups /app/model_cache

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Production: Gunicorn with Uvicorn workers (or single uvicorn for dev)
CMD ["sh", "-c", \
    "if [ \"$DEBUG\" = \"true\" ]; then \
       python -m uvicorn app.main:app --host 0.0.0.0 --port 8000; \
     else \
       gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${WORKERS:-4} \
         --bind 0.0.0.0:8000 --max-requests 10000 --max-requests-jitter 1000 \
         --timeout 120 --graceful-timeout 30 --keep-alive 5; \
     fi"]
