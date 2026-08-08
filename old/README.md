# NHPC Hydro Power Plant Weather Warning & Flood Monitoring System

![CI](https://github.com/Kshitij-Sahdev/nhpc/actions/workflows/ci.yml/badge.svg)
![System Status](https://img.shields.io/badge/System-Operational-brightgreen)
![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Database](https://img.shields.io/badge/Database-SQLite%2FPostgreSQL-orange.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![GIS](https://img.shields.io/badge/GIS-Leaflet.js-green.svg)

An enterprise-grade weather forecasting, flood early warning, and reservoir catchment monitoring system engineered for **NHPC (National Hydroelectric Power Corporation)** power stations across India. 

The system automatically pulls high-resolution Numerical Weather Prediction (NWP) data from the **India Meteorological Department (IMD)**, calculates spatial grid overlays for hydro-electric power stations and catchment basins, detects extreme precipitation and gale events, audits alert state transitions, and renders interactive GIS visual dashboards.

---

## 📑 Table of Contents

- [Executive Overview](#-executive-overview)
- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Weather Warning Threshold Matrix](#-weather-warning-threshold-matrix)
- [Production Database Schema](#-production-database-schema)
- [Installation & Setup](#-installation--setup)
- [Running the System](#-running-the-system)
  - [1. Running Locally](#1-running-locally)
  - [2. Docker Deployment](#2-docker-deployment)
- [REST API Reference](#-rest-api-reference)
- [Alert & Notification Integrations](#-alert--notification-integrations)
- [Testing](#-testing)
- [Health Checks & Observability](#-health-checks--observability)
- [Configuration Reference](#-configuration-reference)
- [Project Directory Structure](#-project-directory-structure)
- [Troubleshooting](#-troubleshooting)
- [License & Support](#-license--support)

---

## 🌊 Executive Overview

Hydro-electric infrastructure requires proactive weather monitoring to manage dam water levels, prevent flash-flood disasters, optimize turbine discharge, and ensure operational safety. 

This platform performs automated, scheduled ingestion of IMD's 0.125° grid MME/GFS numerical forecasts, evaluating 120-hour (5-day) weather trajectories for registered NHPC power stations (such as *Subansiri Lower*, *Teesta Low Dam IV*, *Nimoo Bazgo*, *Chutak*, *Uri I & II*, *Tanakpur*, *Kishanganga*, and *Dibang*).

When critical weather anomalies are detected (e.g. cloudbursts, heavy rainfall > 100mm/24h, or gale winds > 25 m/s), the system automatically triggers multi-channel emergency alerts (Telegram, Slack, Email) and logs state transitions into a persistent, production-level relational database.

---

## 🏗 System Architecture

```
                                +-------------------------------+
                                |  India Meteorological Dept.   |
                                |  (IMD Mausamgram 0.125° GFS)  |
                                +---------------+---------------+
                                                |
                                                v
                                +---------------+---------------+
                                |   imd_ping.py (Grid Sampler)   |
                                +---------------+---------------+
                                                |
                                                v
                                +---------------+---------------+
                                |     update_forecasts.py       |
                                |   - KML Basin Parsing         |
                                |   - 120h Threshold Engine     |
                                |   - State Transition Audit    |
                                +-------+---------------+-------+
                                        |               |
             +--------------------------+               +--------------------------+
             |                                                                     |
             v                                                                     v
+------------+------------+                                           +------------+------------+
|   database.py           |                                           |    Multi-Channel Alerts   |
| (SQLite / PostgreSQL)   |                                           | - Telegram Bot            |
| - plants                |                                           | - Slack Webhook           |
| - forecast_runs         |                                           | - SMTP Email              |
| - plant_forecasts       |                                           +-------------------------+
| - alert_history         |
| - on_demand_forecasts   |
+------------+------------+
             |
             v
+------------+------------+
|     start_server.py     | <--- REST API & Web Dashboard Server (Port 8000 / 80)
+------------+------------+
             |
             v
+------------+------------+
|   Leaflet GIS Dashboard | (Interactive Map, Hourly Weather Curves, Catchment Boundaries)
+-------------------------+
```

---

## ⭐ Key Features

1. **Automated IMD NWP Ingestion**: Queries IMD 3-hourly numerical model runs on a $0.125^\circ \times 0.125^\circ$ coordinate grid.
2. **KML Catchment Parsing**: Automatically extracts dam centroids and polygon boundaries from Spatial KML/SHP files (`Catchment_NHPC.KML`).
3. **Resilient RAM Caching & Stale-on-Error Fallback**: Thread-safe in-memory caching with automatic disaster fallback mode. If IMD upstream servers drop during an emergency, stale telemetry is safely served with a `"stale": true` warning flag instead of crashing.
4. **Nginx Micro-Caching**: Sub-5ms API response latency under high-concurrency burst traffic via Nginx RAM micro-caching (`proxy_cache`).
5. **Production-Grade Database Storage**: Structured relational database (`database.py`) storing power station metadata, historical forecast runs, station metrics, state audit logs, and on-demand queries.
6. **Alert Transition Engine**: Tracks state transitions (`GREEN` $\rightarrow$ `YELLOW` $\rightarrow$ `RED`) to prevent duplicate notification spam while auditing status escalations.
7. **Interactive GIS Dashboard**: Leaflet-powered GIS dashboard featuring dark-mode map tiles, color-coded station markers, interactive catchment polygon overlays, search/filtering, and detailed hourly charts (rainfall, temperature, wind, humidity, cloud cover).
8. **On-Demand Location Forecasting**: Users can click any coordinate on the map or query custom locations via `/api/forecast` to instantly generate a 5-day weather analysis.
9. **Containerized Deployment**: Ready-to-deploy `Dockerfile` and `docker-compose.yml` with automated 6-hour cron scraping, Nginx reverse proxy, and persistent Docker volumes.
10. **Automated Enterprise Test Suite**: Comprehensive `unittest` test suite covering DB schemas, weather alerts, API security, and RAM cache latency (`python -m unittest discover tests`).

---

## 🚨 Weather Warning Threshold Matrix

| Alert Level | Indicator | Meteorological Condition | Recommended Operational Action |
| :--- | :--- | :--- | :--- |
| **RED ALERT** | 🔴 High Risk | • 3-hour peak rainfall $> 30.0 \text{ mm}$<br>• 24-hour cumulative rainfall $> 100.0 \text{ mm}$ | Emergency flood protocol, notify dam operators, prepare spillway gates, issue downstream public safety warnings. |
| **YELLOW WATCH** | 🟡 Medium Risk | • 3-hour peak rainfall $> 15.0 \text{ mm}$<br>• 24-hour cumulative rainfall $> 50.0 \text{ mm}$<br>• Wind gusts $> 25.0 \text{ m/s}$ | Increased monitoring frequency, inspect catchment tributaries, prepare emergency standby teams. |
| **GREEN SAFE** | 🟢 Low Risk | • Normal weather window within safe limits | Standard routine power generation and reservoir management. |
| **UNKNOWN** | ⚪ Fetch Error | • Connection timeout / missing model data | Verify IMD Mausamgram server connectivity. |

---

## 🗄 Production Database Schema

The system uses an optimized relational database (`data/nhpc_weather.db`) with Foreign Keys, indexed columns, and strict state transaction logging:

```sql
-- 1. Power Plants Metadata
CREATE TABLE plants (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    document TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    boundaries_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Forecast Scraping Execution Cycles
CREATE TABLE forecast_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_run_time TEXT NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_plants INTEGER NOT NULL,
    red_count INTEGER NOT NULL,
    yellow_count INTEGER NOT NULL,
    green_count INTEGER NOT NULL,
    unknown_count INTEGER NOT NULL
);

-- 3. Station Weather Metrics Per Forecast Run
CREATE TABLE plant_forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_run_id INTEGER NOT NULL,
    plant_id TEXT NOT NULL,
    plant_name TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    alert_level TEXT NOT NULL,
    rain_24h REAL DEFAULT 0.0,
    rain_48h REAL DEFAULT 0.0,
    rain_72h REAL DEFAULT 0.0,
    max_3h_rain REAL DEFAULT 0.0,
    max_wind REAL DEFAULT 0.0,
    max_gust REAL DEFAULT 0.0,
    reasons_json TEXT,
    summary_json TEXT,
    forecast_details_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(forecast_run_id) REFERENCES forecast_runs(id) ON DELETE CASCADE
);

-- 4. Alert Status Transition History (Auditing)
CREATE TABLE alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_id TEXT NOT NULL,
    plant_name TEXT NOT NULL,
    old_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    reasons_json TEXT,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. On-Demand Custom Coordinate Queries
CREATE TABLE on_demand_forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id TEXT NOT NULL,
    plant_name TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    alert_level TEXT NOT NULL,
    summary_json TEXT,
    forecast_json TEXT,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Useful SQL Queries

```sql
-- Query stations currently under RED or YELLOW alerts from latest run
SELECT plant_name, alert_level, rain_24h, max_3h_rain, max_wind
FROM plant_forecasts
WHERE forecast_run_id = (SELECT MAX(id) FROM forecast_runs)
  AND alert_level IN ('RED', 'YELLOW');

-- View recent alert state escalations
SELECT plant_name, old_status, new_status, reasons_json, triggered_at
FROM alert_history
ORDER BY id DESC LIMIT 20;
```

---

## 🛠 Installation & Setup

### Prerequisites
- **Python**: `3.9` or higher
- **Pip**: Latest version
- **Docker & Docker Compose** *(Optional, for containerized hosting)*

### Step 1: Clone Repository
```bash
git clone https://github.com/Kshitij-Sahdev/nhpc.git
cd nhpc
```

### Step 2: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env` and fill in your alert credentials:
```bash
cp .env.example .env
```

Example `.env` configuration:
```env
# Telegram Notification Settings
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_or_channel_here

# Slack Webhook Settings
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Email Notification Settings (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
ALERT_RECIPIENT_EMAIL=dam_safety_officer@nhpc.gov.in
```

---

## 🚀 Running the System

### 1. Running Locally

#### Execute Forecast Scraper & Database Update
```bash
python update_forecasts.py
```
This will:
- Parse `Catchment_NHPC.KML`
- Initialize `data/nhpc_weather.db`
- Ingest IMD weather forecast grids
- Store records in SQLite DB and update web cache files (`web/forecasts.json`, `web/forecast_data.js`)
- Write summary report to `weather_forecast_summary.txt`
- Dispatch alerts if state transitions occur

#### Launch Local Web Server & API
```bash
python start_server.py
```
This starts the HTTP server at `http://localhost:8000/index.html` and opens the dashboard in your default browser.

---

### 2. Docker Deployment

To build and launch the production container with automatic 6-hourly scraping and Nginx web hosting:

```bash
docker-compose up --build -d
```

Check container status and logs:
```bash
docker-compose logs -f nhpc-dashboard
```

To stop the container:
```bash
docker-compose down
```

---

## 📡 REST API Reference

The built-in HTTP server (`start_server.py`) provides the following REST API endpoints:

### 1. On-Demand Coordinate Forecast
- **Endpoint**: `GET /api/forecast?lat={LAT}&lon={LON}&name={NAME}`
- **Description**: Computes 5-day weather analysis for any arbitrary coordinates on earth.
- **Response**:
```json
{
  "id": "custom-31-2000-77-1000",
  "name": "Custom Dam Site",
  "lat": 31.2,
  "lon": 77.1,
  "alert_level": "YELLOW",
  "reasons": ["Heavy peak rainfall of 18.5 mm in 3h expected at 2026-07-25 14:00"],
  "summary": {
    "rain_24h": 42.1,
    "rain_48h": 68.3,
    "max_3h_rain": 18.5,
    "max_wind": 8.4
  },
  "forecast": { ... }
}
```

### 2. List Registered Power Stations
- **Endpoint**: `GET /api/plants`
- **Description**: Returns all hydro plants stored in the database.

### 3. Fetch Alert Transition History
- **Endpoint**: `GET /api/alerts` (or `/api/history`)
- **Description**: Returns audit log of recent alert level changes.

### 4. Fetch Latest Database Forecast Run
- **Endpoint**: `GET /api/latest`
- **Description**: Returns latest scrape run details and station weather summary.

---

## 📬 Alert & Notification Integrations

When a station escalates from `GREEN` $\rightarrow$ `YELLOW` or `YELLOW` $\rightarrow$ `RED`, emergency alerts are automatically dispatched:

- **Telegram**: Sends formatted Markdown alerts with peak rainfall details and coordinates.
- **Slack**: Sends color-coded Slack attachments (`#ff0000` for RED, `#ffcc00` for YELLOW).
- **Email**: Sends HTML emails to dam safety officers with detailed meteorological breakdown.

---

## 🧪 Testing

The project uses **pytest** with comprehensive unit, integration, and regression tests.

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run full test suite
pytest -v

# Run with coverage report
pytest --cov=. --cov-report=term-missing -v

# Run only unit tests (fast, no network)
pytest -m unit -v

# Run only integration tests
pytest -m integration -v

# Run regression tests (frozen IMD fixtures)
pytest -m regression -v
```

---

## 🔍 Health Checks & Observability

### Kubernetes-Compatible Probes

| Endpoint | Purpose | Checks |
|----------|---------|--------|
| `GET /api/liveness` | Liveness probe | Process is running (no deps) |
| `GET /api/readiness` | Readiness probe | DB connected + forecast < 12h old |
| `GET /api/health` | Full health check | DB, disk, uptime, last forecast |

### Prometheus Metrics

`GET /metrics` exposes application metrics:
- `nhpc_http_request_duration_seconds` — API latency histogram
- `nhpc_http_requests_total` — Request counter by endpoint/status
- `nhpc_forecast_update_duration_seconds` — Scraper cycle duration
- `nhpc_active_alerts` — Current alert count by level
- `nhpc_imd_request_duration_seconds` — IMD API latency
- `nhpc_db_query_duration_seconds` — Database query latency

### API Documentation

- **Redoc UI**: `http://localhost:8000/api/docs`
- **OpenAPI Spec**: `http://localhost:8000/api/openapi.yaml`

---

## ⚙️ Configuration Reference

All settings are configured via `.env` file or environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_PORT` | `8000` | HTTP server port |
| `APP_ENV` | `development` | `development` or `production` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FORMAT` | `text` | `text` (colored) or `json` (structured) |
| `DB_PATH` | `data/nhpc_weather.db` | SQLite database path |
| `DB_CLEANUP_DAYS` | `90` | Data retention period |
| `IMD_BASE_URL` | `https://mausamgram.imd.gov.in` | IMD API base URL |
| `IMD_REQUEST_TIMEOUT` | `10` | HTTP timeout (seconds) |
| `IMD_MAX_RETRIES` | `2` | Retry attempts |
| `IMD_CACHE_TTL` | `1800` | Forecast cache TTL (seconds) |
| `RATE_LIMIT_RPM` | `60` | API rate limit per IP |
| `TELEGRAM_BOT_TOKEN` | — | Telegram Bot API token |
| `TELEGRAM_CHAT_ID` | — | Telegram chat/channel ID |
| `SLACK_WEBHOOK_URL` | — | Slack webhook URL |
| `SMTP_SERVER` | — | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | — | SMTP username |
| `SMTP_PASSWORD` | — | SMTP password |
| `ALERT_RECIPIENT_EMAIL` | — | Alert recipient |

---

## 📁 Project Directory Structure

```
nhpc/
├── Catchment_NHPC.KML            # Spatial boundary data for NHPC power stations
├── Dockerfile                    # Containerization (Nginx + Python scraper loop)
├── README.md                     # Enterprise documentation (this file)
├── config.py                     # Centralized configuration (pydantic-settings)
├── log.py                        # Structured logging utilities (JSON/colored)
├── exceptions.py                 # Custom exception hierarchy
├── metrics.py                    # Prometheus metrics definitions
├── database.py                   # Production SQLite database layer
├── imd_ping.py                   # IMD API client with cache & disaster fallback
├── update_forecasts.py           # Forecast processor & alert engine
├── start_server.py               # HTTP server & REST API
├── backup_db.py                  # Database backup utility
├── openapi.yaml                  # OpenAPI 3.0 API specification
├── docker-compose.yml            # Docker orchestration
├── requirements.txt              # Production dependencies
├── requirements-dev.txt          # Development dependencies
├── pyproject.toml                # Tool config (ruff, mypy, pytest)
├── .pre-commit-config.yaml       # Git pre-commit hooks
├── .env.example                  # Configuration template
├── .dockerignore                 # Docker build context filter
├── .github/
│   └── workflows/ci.yml          # CI/CD pipeline (GitHub Actions)
├── data/
│   ├── alert_state.json          # Alert status tracker
│   ├── nhpc_weather.db           # Persistent SQLite database
│   └── backups/                  # Automated database backups
├── tests/
│   ├── conftest.py               # Pytest fixtures
│   ├── test_database.py          # Database unit tests
│   ├── test_imd_ping.py          # IMD scraper unit tests
│   ├── test_forecast_analysis.py # Alert analysis unit tests
│   ├── test_api.py               # API integration tests
│   ├── test_parser.py            # KML parser unit tests
│   ├── test_regression.py        # Regression tests (frozen fixtures)
│   └── test_nhpc_system.py       # Legacy test suite
└── web/
    ├── app.js                    # Leaflet map, Chart.js, UI logic
    ├── index.html                # Dashboard UI
    └── styles.css                # Dark-mode glassmorphism stylesheet
```

---

## ❓ Troubleshooting

**Q: The scraper shows "IMD API unreachable" errors.**
A: IMD Mausamgram servers can be intermittently unavailable. The system automatically retries (2 attempts with backoff) and serves cached data during outages. Check `https://mausamgram.imd.gov.in` availability.

**Q: Health check shows "degraded" status.**
A: This means the database is unreachable. Check that `data/nhpc_weather.db` exists and has correct file permissions.

**Q: Alerts are not being sent.**
A: Verify `.env` credentials. Check logs for "not configured — skipping" messages. For Gmail SMTP, use an App Password, not your account password.

**Q: Docker container fails to start.**
A: Check `docker-compose logs -f nhpc-dashboard`. Common issues: port 80 already in use, `.env` file missing.

**Q: Tests fail with import errors.**
A: Run `pip install -r requirements-dev.txt` to install test dependencies.

---

## 📄 License & Support

Developed for **NHPC Hydro Power Plant Weather Warning & Flood Monitoring**.
For system inquiries, feature requests, or technical support, contact the Dam Safety & Weather Operations Team.
