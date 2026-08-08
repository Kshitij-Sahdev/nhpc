# NDMA GeoAlert Dashboard
Selectively filtering NDMA Alerts based on Prioritized States

## Requirements
### System Dependencies
- python (v3.14.5)
- python-pip
- python-virtualenv
- mysql (v8.0.46)
### Python Dependencies
```
annotated-types==0.7.0
APScheduler==3.11.2
blinker==1.9.0
certifi==2026.4.22
charset-normalizer==3.4.7
click==8.3.3
feedparser==6.0.12
Flask==3.1.3
greenlet==3.5.0
gunicorn==26.0.0
idna==3.15
isort==8.0.1
itsdangerous==2.2.0
Jinja2==3.1.6
lance-namespace==0.7.7
lance-namespace-urllib3-client==0.7.7
MarkupSafe==3.0.3
numpy==2.4.6
packaging==26.2
pyarrow==24.0.0
pydantic==2.13.4
pydantic_core==2.46.4
PyMySQL==1.1.3
pyproj==3.7.2
python-dateutil==2.9.0.post0
python-dotenv==1.2.2
requests==2.34.2
sgmllib3k==1.0.0
shapely==2.1.2
six==1.17.0
typing-inspection==0.4.2
typing_extensions==4.15.0
tzlocal==5.3.1
urllib3==2.7.0
Werkzeug==3.1.8
```

## Setup
Clone repository:
```shell
git clone https://github.com/FelicityIris/ndma-alerts-filter
cd ndma-alerts-filter
```
Create Virtual Environment:
```shell
python -m venv venv
source venv/bin/activate
```
Install Python Dependencies:
```shell
pip install -r requirements.txt
```
Configure `.env`:
```.env
# Flask App
FLASK_APP=run.py
FLASK_DEBUG=1

# Cert
# If needed otherwise leave blank
DB_CA_CERT=<path/to/cert>

# Flask Session Key
# Generate using `python -c "import secrets; print(secrets.token_hex(32))"`
SECRET_KEY=<generated_session_key>

# Public API Bearer Token
# Generate using `openssl rand -hex 32`
PUBLIC_API_TOKEN=<generated_token>

# DB Auth
DB_USER=<mysql_user_name>
DB_PASSWORD=<mysql_user_password>
DB_HOST=<hostname>
DB_PORT=<port>
DB_NAME=<mysql_database_name>

# Data
# Add corresponding csv files inside project root and put addresses here
DISTRICTS_DATA=</path/to/csv-file>
STATES_DATA=</path/to/csv-file>
PROJECT_SITES_DATA=</path/to/csv-file>
GND_SITES_DATA=<path/to/csv-file>

# Admin Auth
# Generate using `python ./scripts/generate_password_hash.py`
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=<hashed_password>
```
**\* Add necessary csv files containing districts, states, projects and g&d sites data within the project dierctory.**

## Run
### Debug
```shell
flask --app run.py run --debug
```
### Deploy
```shell
mkdir -p logs/

gunicorn run:app \
  --workers 1 \
  --worker-class gthread \
  --threads 4 \
  --bind 0.0.0.0:5000 \
  --timeout 120 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log \
  --log-level info
```

## References
- [NDMA Sachet Portal](https://sachet.ndma.gov.in/) - Primary source of all Alert Information by NDMA
- [Flask](https://palletsprojects.com/projects/flask/) - Backend Technology
- [MySQL](https://www.mysql.com/) - Database
- [Shapely](https://github.com/shapely/shapely) & [pyproj](https://github.com/pyproj4/pyproj) - Coordinate based Proximity Analysis to generate per-Project Warnings
- [Gunicorn](https://gunicorn.org/) - Production deployment
- [Leaflet](https://leafletjs.com/) - Map display on Home Page
- [Leaflet Textpath Plugin](https://github.com/makinacorpus/Leaflet.TextPath) - Leaflet plugin to show label text along polylines
- [Catppuccin Color Pallete](https://catppuccin.com/) - Color and Design Aesthetics
- [Lucide Icons](https://lucide.dev/) - UI Icons
- [Community Created Maps of India](https://projects.datameet.org/maps/) - Official Boundary of India
- [Open Government Data (OGD) Platform India](https://www.data.gov.in/catalog/boundaries-water-resources-projects) - Indian Rivers Polygon Data