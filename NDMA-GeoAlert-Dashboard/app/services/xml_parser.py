import logging
import time
import xml.etree.ElementTree as ET

from dateutil import parser

from app.services.http_client import session
from app.services.settings_service import get_settings

NAMESPACE = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}


def fetch_resource_xml(url):
    settings = get_settings()
    max_retries = int(settings["max_retries"])
    retry_delay = int(settings["retry_delay_seconds"])
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as error_msg:
            logging.error(f"Resource fetch failed for: {url}")
            logging.info(
                f"Trying again in {retry_delay} seconds. Attempt: {attempt+1} / {max_retries}"
            )
            logging.error(f"{error_msg}")

            if attempt == max_retries - 1:
                raise

            time.sleep(retry_delay)


def parse_polygon_xml(xml_data):
    root = ET.fromstring(xml_data)
    polygons = []
    polygon_elements = root.findall(".//polygon")
    for polygon_element in polygon_elements:
        polygon_text = polygon_element.text
        if polygon_text:
            polygons.append(polygon_text.strip())
    return polygons


def extract_polygon_url(root):
    parameters = root.findall(".//cap:parameter", namespaces=NAMESPACE)
    for parameter in parameters:
        value_name = parameter.findtext("cap:valueName", namespaces=NAMESPACE)
        value = parameter.findtext("cap:value", namespaces=NAMESPACE)
        if value_name == "Polygon URL":
            return value
    return None


def extract_english_headline(root):
    info_blocks = root.findall(".//cap:info", namespaces=NAMESPACE)
    for info in info_blocks:
        language = info.findtext("cap:language", namespaces=NAMESPACE)
        if language and language.startswith("en"):
            headline = info.findtext("cap:headline", namespaces=NAMESPACE)
            return headline
    return None


def extract_district_codes(root):
    district_codes = []
    geocodes = root.findall(".//cap:geocode", namespaces=NAMESPACE)
    for geocode in geocodes:
        value_name = geocode.findtext("cap:valueName", namespaces=NAMESPACE)
        value = geocode.findtext("cap:value", namespaces=NAMESPACE)
        if value_name == "LGD District Code":
            if value:
                district_codes.append(int(value.strip()))
    return district_codes


def parse_datetime(value):
    if not value:
        return None
    return parser.parse(value)


def parse_alert_xml(xml_data):
    root = ET.fromstring(xml_data)

    alert_data = {}
    alert_data["identifier"] = (
        (root.findtext(".//cap:identifier", namespaces=NAMESPACE))
        .split("-")[1]
        .split("_")[0]
    )
    alert_data["event"] = root.findtext(".//cap:event", namespaces=NAMESPACE)
    alert_data["headline_en"] = extract_english_headline(root)
    alert_data["severity"] = root.findtext(".//cap:severity", namespaces=NAMESPACE)
    alert_data["urgency"] = root.findtext(".//cap:urgency", namespaces=NAMESPACE)
    alert_data["certainty"] = root.findtext(".//cap:certainty", namespaces=NAMESPACE)
    alert_data["effective"] = parse_datetime(
        root.findtext(".//cap:effective", namespaces=NAMESPACE)
    )
    alert_data["onset"] = parse_datetime(
        root.findtext(".//cap:onset", namespaces=NAMESPACE)
    )
    alert_data["expires"] = parse_datetime(
        root.findtext(".//cap:expires", namespaces=NAMESPACE)
    )

    polygon_url = extract_polygon_url(root)
    polygons = []
    if polygon_url:
        try:
            polygon_xml = fetch_resource_xml(polygon_url)
            polygons = parse_polygon_xml(polygon_xml)
        except Exception as error:
            logging.error(f"Failed to fetch polygon: {polygon_url}")
            logging.error(error)
    alert_data["polygons"] = polygons

    alert_data["district_codes"] = extract_district_codes(root)

    return alert_data


def fetch_and_parse_alert(url):
    xml_data = fetch_resource_xml(url)
    return parse_alert_xml(xml_data)
