import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.rules_engine import run_nightly_rules
from app.services.sms.outbox_worker import process_outbox_batch

logger = logging.getLogger("garuka.jobs.scheduler")

scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.APP_TZ))


async def nightly_rules_job() -> None:
    logger.info("Executing scheduled nightly rules job...")
    async with AsyncSessionLocal() as db:
        try:
            summary = await run_nightly_rules(db)
            logger.info("Nightly rules job completed successfully: %s", summary)
        except Exception:
            logger.exception("Nightly rules job failed")


async def sms_outbox_job() -> None:
    async with AsyncSessionLocal() as db:
        try:
            processed = await process_outbox_batch(db)
            if processed > 0:
                logger.info("Dispatched %d scheduled SMS message(s)", processed)
        except Exception:
            logger.exception("SMS outbox job failed")


def start_scheduler() -> None:
    # 00:30 Africa/Kigali every day
    scheduler.add_job(
        nightly_rules_job,
        trigger=CronTrigger(hour=0, minute=30, timezone=ZoneInfo(settings.APP_TZ)),
        id="nightly_rules",
        name="Nightly Rules Engine Evaluation",
        replace_existing=True,
    )

    # Every 30 seconds for pending SMS outbox dispatch
    scheduler.add_job(
        sms_outbox_job,
        trigger=IntervalTrigger(seconds=30),
        id="sms_outbox_dispatch",
        name="SMS Outbox Dispatcher",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Garuka background scheduler started (TZ=%s)", settings.APP_TZ)


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Garuka background scheduler shutdown")
