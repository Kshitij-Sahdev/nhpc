# Production Dockerfile for Coolify Deployment
FROM python:3.11-slim

LABEL maintainer="NHPC Hydro Power Plant Catchment Emergency Warning System"
LABEL description="Unified Catchment GIS & NDMA Emergency Disaster Alert Terminal"

# Prevent Python from writing .pyc files and enable unbuffered log output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_PORT=8000
ENV FLASK_ENV=production

# Install system dependencies required for Shapely, PyProj & geospatial math
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    g++ \
    libgeos-dev \
    proj-bin \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and spatial datasets
COPY app/ ./app/
COPY run.py .
COPY config.py .
COPY database.py .
COPY spatial_engine.py .
COPY warning_service.py .
COPY imd_ping.py .
COPY update_forecasts.py .
COPY ndma_service.py .
COPY Catchment_NHPC.KML .
COPY Catchment_NHPC.json .

# Create data directory for persistent SQLite database
RUN mkdir -p /app/data

# Expose application port
EXPOSE 8000

# Health check to ensure Coolify knows when application is healthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/catchments/status || exit 1

# Launch application entrypoint (Flask + APScheduler)
CMD ["python", "run.py"]
