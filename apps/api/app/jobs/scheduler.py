import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.rules_engine import run_nightly_rules
from app.services.sms.outbox_worker import process_outbox_batch

logger = logging.getLogger("garuka.jobs.scheduler")

scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.APP_TZ))

# Well-known 32-bit positive integer IDs for PostgreSQL advisory locks
LOCK_ID_NIGHTLY_RULES = 42000001
LOCK_ID_SMS_OUTBOX = 42000002


@asynccontextmanager
async def try_acquire_job_lock(
    db: AsyncSession, lock_id: int
) -> AsyncGenerator[bool, None]:
    """
    Attempts to acquire a non-blocking PostgreSQL session advisory lock.
    Yields True if acquired, False if another worker is currently executing the job.
    Automatically unlocks on exit.
    """
    acquired = False
    try:
        res = await db.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": lock_id}
        )
        acquired = bool(res.scalar())
    except Exception as exc:
        logger.warning(
            "Could not execute pg_try_advisory_lock (possibly non-PostgreSQL DB): %s",
            exc,
        )
        acquired = True

    try:
        yield acquired
    finally:
        if acquired:
            try:
                await db.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id}
                )
            except Exception:
                pass


async def nightly_rules_job() -> None:
    async with AsyncSessionLocal() as db:
        async with try_acquire_job_lock(db, LOCK_ID_NIGHTLY_RULES) as acquired:
            if not acquired:
                logger.info("Nightly rules job is already running on another worker. Skipping duplicate execution.")
                return

            logger.info("Executing scheduled nightly rules job...")
            try:
                summary = await run_nightly_rules(db)
                logger.info("Nightly rules job completed successfully: %s", summary)
            except Exception:
                logger.exception("Nightly rules job failed")


async def sms_outbox_job() -> None:
    async with AsyncSessionLocal() as db:
        async with try_acquire_job_lock(db, LOCK_ID_SMS_OUTBOX) as acquired:
            if not acquired:
                # Silently skip if another worker process is already dispatching
                return

            try:
                processed = await process_outbox_batch(db)
                if processed > 0:
                    logger.info("Dispatched %d scheduled SMS message(s)", processed)
            except Exception:
                logger.exception("SMS outbox job failed")


def start_scheduler() -> None:
    if not settings.SCHEDULER_ENABLED:
        logger.info("Background scheduler is disabled via SCHEDULER_ENABLED=false")
        return

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


if __name__ == "__main__":
    # Standalone dedicated worker entrypoint
    from app.core.logging import setup_logging

    setup_logging()
    logger.info("Starting Garuka dedicated scheduler worker...")
    start_scheduler()
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        shutdown_scheduler()
