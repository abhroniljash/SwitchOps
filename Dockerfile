# Multi-stage production build for SwitchOps
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (git for GitOps, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PORT=5000 \
    HOST=0.0.0.0 \
    SQLITE_DB_PATH=/app/data/switchops.db

# Ensure persistence directory exists
RUN mkdir -p /app/data

EXPOSE 5000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/integrations/health || exit 1

# Start production WSGI server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "switchops.web.app:app"]
