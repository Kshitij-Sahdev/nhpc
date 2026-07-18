FROM python:3.9-slim

# Install Nginx
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files
COPY Catchment_NHPC.KML .
COPY imd_ping.py .
COPY update_forecasts.py .

# Copy web files
COPY web/ ./web/

# Configure Nginx to serve the web directory
RUN echo 'server { \
    listen 80; \
    location / { \
        root /app/web; \
        index index.html; \
        try_files $uri $uri/ =404; \
    } \
}' > /etc/nginx/sites-available/default

# Create startup entrypoint script
RUN echo '#!/bin/sh\n\
# Start nginx in the background\n\
nginx\n\
\n\
# Loop indefinitely running scraper every 6 hours in the foreground\n\
while true; do\n\
    echo "[Scraper Log] Executing forecast scrape..."\n\
    python update_forecasts.py\n\
    echo "[Scraper Log] Finished forecast scrape. Next run in 6 hours."\n\
    sleep 21600\n\
done' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Expose port 80 for Nginx
EXPOSE 80

# Run entrypoint script
CMD ["/app/entrypoint.sh"]
