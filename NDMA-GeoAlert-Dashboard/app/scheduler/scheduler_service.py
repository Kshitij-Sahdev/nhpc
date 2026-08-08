from apscheduler.schedulers.background import BackgroundScheduler

from app.services.ingestion_service import ingest_alerts
from app.services.settings_service import get_settings

scheduler = BackgroundScheduler()


def reload_scheduler():
    settings = get_settings()
    interval_minutes = max(5, int(settings["scheduler_minutes"]))

    scheduler.remove_all_jobs()

    scheduler.add_job(
        ingest_alerts,
        trigger="interval",
        minutes=interval_minutes,
        id="alert_ingestion",
        replace_existing=True,
        max_instances=1,
    )

    print(f"Scheduler configured @ {interval_minutes} minute interval.")


def start_scheduler():
    reload_scheduler()

    if not scheduler.running:
        scheduler.start()

    print("Scheduler started.")
