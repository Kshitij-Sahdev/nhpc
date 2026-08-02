import logging
import time

from app.services.alert_service import (
    alert_exists,
    delete_expired_alerts,
    is_alert_expired,
    save_alert,
)
from app.services.feed_fetcher import extract_identifer_from_link, get_alert_links
from app.services.settings_service import get_settings
from app.services.state_service import get_selected_states
from app.services.warning_service import refresh_warnings
from app.services.xml_parser import fetch_and_parse_alert


def ingest_alerts():
    selected_states = get_selected_states()
    settings = get_settings()
    request_delay = int(settings["request_delay_seconds"])

    for state in selected_states:
        state_id = state["state_id"]
        feed_slug = state["feed_slug"]
        try:
            alert_links = get_alert_links(feed_slug)

            if not alert_links:
                continue

            for link in alert_links:
                try:
                    identifier = extract_identifer_from_link(link)
                    if alert_exists(identifier):
                        logging.info(f"XML already in DB, skipping [ID: {identifier}]")
                        continue
                    alert_data = fetch_and_parse_alert(link)
                    if is_alert_expired(alert_data):
                        logging.info(
                            f"XML expired, skipping [ID: {alert_data['identifier']}]"
                        )
                        continue
                    save_alert(alert_data, state_id)
                    logging.info(f"Saved XML in DB [ID: {alert_data['identifier']}]")
                except Exception as error:
                    logging.error(f"Error: Failed to fetch XML [Link: {link}]")
                    logging.error(error)
                finally:
                    logging.info(f"Fetching next XML in { request_delay } seconds.")
                    time.sleep(request_delay)
        except Exception as error_msg:
            logging.error(
                f"Error: Failed to fetch RSS Feed [State Feed Slug: {feed_slug}]"
            )
            logging.error(error_msg)
    logging.info("Data ingestion complete")

    logging.info("Deleting expired XMLs")
    delete_expired_alerts()

    logging.info("Generating new warnings")
    refresh_warnings()
