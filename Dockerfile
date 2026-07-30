FROM python:3.9-slim

# Install Nginx and supervisord for process management
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for running the application
RUN useradd -m -r -s /bin/false appuser

# Set up working directory
WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files
COPY Catchment_NHPC.KML .
COPY imd_ping.py .
COPY database.py .
COPY update_forecasts.py .
COPY start_server.py .

# Copy web files
COPY web/ ./web/

# Create data directory with proper permissions
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Configure Nginx: micro-caching + static files + reverse proxy API
RUN echo 'proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m max_size=50m inactive=15m use_temp_path=off; \
server { \
    listen 80; \
    server_name _; \
    \
    # Security headers \
    add_header X-Content-Type-Options "nosniff" always; \
    add_header X-Frame-Options "DENY" always; \
    add_header X-XSS-Protection "1; mode=block" always; \
    add_header Referrer-Policy "strict-origin-when-cross-origin" always; \
    \
    # Static web files \
    location / { \
        root /app/web; \
        index index.html; \
        try_files $uri $uri/ =404; \
    } \
    \
    # Reverse proxy API requests to Python server with micro-caching \
    location /api/ { \
        proxy_pass http://127.0.0.1:8000; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
        proxy_cache api_cache; \
        proxy_cache_valid 200 60s; \
        proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504; \
        add_header X-Cache-Status $upstream_cache_status; \
        proxy_connect_timeout 10s; \
        proxy_read_timeout 60s; \
        proxy_send_timeout 10s; \
    } \
}' > /etc/nginx/sites-available/default

# Configure supervisord to manage all 3 processes
RUN echo '[supervisord]\n\
nodaemon=true\n\
user=root\n\
logfile=/var/log/supervisor/supervisord.log\n\
pidfile=/var/run/supervisord.pid\n\
\n\
[program:nginx]\n\
command=nginx -g "daemon off;"\n\
autostart=true\n\
autorestart=true\n\
priority=10\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
\n\
[program:api_server]\n\
command=python /app/start_server.py\n\
directory=/app\n\
user=appuser\n\
autostart=true\n\
autorestart=true\n\
priority=20\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
\n\
[program:scraper]\n\
command=/app/scraper_loop.sh\n\
directory=/app\n\
user=appuser\n\
autostart=true\n\
autorestart=true\n\
priority=30\n\
startsecs=5\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0' > /etc/supervisor/conf.d/nhpc.conf

# Create scraper loop script with proper signal handling
RUN echo '#!/bin/sh\n\
\n\
# Graceful shutdown handler\n\
cleanup() {\n\
    echo "[Scraper] Received shutdown signal. Exiting gracefully..."\n\
    exit 0\n\
}\n\
\n\
trap cleanup SIGTERM SIGINT SIGHUP\n\
\n\
echo "[Scraper] Starting forecast scrape loop (every 6 hours)..."\n\
\n\
# Run immediately on startup\n\
echo "[Scraper] Executing initial forecast scrape..."\n\
python /app/update_forecasts.py\n\
echo "[Scraper] Initial scrape complete."\n\
\n\
# Loop indefinitely with proper signal handling\n\
while true; do\n\
    echo "[Scraper] Next run in 6 hours. Sleeping..."\n\
    sleep 21600 &\n\
    wait $!\n\
    echo "[Scraper] Executing forecast scrape..."\n\
    python /app/update_forecasts.py\n\
    echo "[Scraper] Finished forecast scrape."\n\
done' > /app/scraper_loop.sh && chmod +x /app/scraper_loop.sh

# Create supervisor log directory
RUN mkdir -p /var/log/supervisor

# Expose port 80 for Nginx
EXPOSE 80

# Health check: verify Nginx is serving and API is responding
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:80/ > /dev/null 2>&1 && \
        curl -f http://localhost:8000/api/health > /dev/null 2>&1 || exit 1

# Run supervisord as PID 1 (manages nginx + api_server + scraper)
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/nhpc.conf"]
