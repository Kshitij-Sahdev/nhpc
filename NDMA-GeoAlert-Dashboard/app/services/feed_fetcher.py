import logging
import time
from urllib.parse import parse_qs, urlparse

import feedparser

from app.services.feed_cache_service import get_feed_cache, update_feed_cache
from app.services.http_client import session
from app.services.settings_service import get_settings

BASE_RSS_URL = "https://sachet.ndma.gov.in/cap_public_website/rss/"


def generate_feed_url(feed_slug):
    return f"{BASE_RSS_URL}rss_{feed_slug}.xml"


def fetch_rss_feed(feed_slug):
    settings = get_settings()
    max_retries = int(settings["max_retries"])
    retry_delay = int(settings["retry_delay_seconds"])
    url = generate_feed_url(feed_slug)

    cached_feed = get_feed_cache(feed_slug)
    headers = {}
    if cached_feed:
        if cached_feed["etag"]:
            headers["If-None-Match"] = cached_feed["etag"]
        if cached_feed["last_modified"]:
            headers["If-Modified-Since"] = cached_feed["last_modified"]

    for attempt in range(max_retries):
        try:
            response = session.get(url, headers=headers, timeout=10)

            if response.status_code == 304:
                logging.info(
                    f"RSS Feed Unchanged, skipping [State Feed Slug: {feed_slug}]"
                )
                return None

            response.raise_for_status()

            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
            update_feed_cache(feed_slug, etag, last_modified)

            return response.text
        except Exception as error_msg:
            logging.error(
                f"Error: Failed to fetch RSS Feed [State Feed Slug: {feed_slug}]"
            )
            logging.info(
                f"Trying again in {retry_delay} seconds. Attempt: {attempt+1} / {max_retries}"
            )
            logging.error(f"{error_msg}")

            if attempt == max_retries - 1:
                raise

            time.sleep(retry_delay)


def extract_alert_links(rss_data):
    parsed_feed = feedparser.parse(rss_data)
    links = []
    for entry in parsed_feed.entries:
        link = entry.get("link")
        if link:
            links.append(link)
    return links


def get_alert_links(feed_slug):
    rss_data = fetch_rss_feed(feed_slug)

    if not rss_data:
        return []

    return extract_alert_links(rss_data)


def extract_identifer_from_link(link):
    parsed_url = urlparse(link)
    query_params = parse_qs(parsed_url.query)
    identifier = query_params.get("identifier", [None])[0]
    return identifier
