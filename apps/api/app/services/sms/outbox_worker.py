import logging
import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import utc_now
from app.models.messaging import SmsOutbox, SmsStatusEnum
from app.services.sms.at_provider import AfricasTalkingSmsProvider
from app.services.sms.console_provider import ConsoleSmsProvider
from app.services.sms.provider import SmsProvider

logger = logging.getLogger("garuka.sms.outbox")

EXEMPT_TEMPLATES = {"parent_visit_code"}


def get_sms_provider() -> SmsProvider:
    if settings.SMS_PROVIDER == "africastalking":
        return AfricasTalkingSmsProvider()
    return ConsoleSmsProvider()


def is_in_quiet_hours(dt: datetime | None = None) -> bool:
    tz = ZoneInfo(settings.APP_TZ)
    local_dt = (dt or datetime.now(UTC)).astimezone(tz)
    local_time = local_dt.time()

    start_h, start_m = map(int, settings.SMS_QUIET_HOURS_START.split(":"))
    end_h, end_m = map(int, settings.SMS_QUIET_HOURS_END.split(":"))
    quiet_start = time(start_h, start_m)
    quiet_end = time(end_h, end_m)

    if quiet_start > quiet_end:
        # Crosses midnight e.g. 19:00 to 07:00
        return local_time >= quiet_start or local_time < quiet_end
    return quiet_start <= local_time < quiet_end


def compute_scheduled_at(template_key: str) -> datetime:
    """
    Computes scheduled dispatch time in UTC.
    Transactional visit codes bypass quiet hours.
    Notifications during quiet hours are deferred until 07:00 Kigali time.
    """
    now_utc = utc_now()
    if template_key in EXEMPT_TEMPLATES:
        return now_utc

    if not is_in_quiet_hours(now_utc):
        return now_utc

    tz = ZoneInfo(settings.APP_TZ)
    local_now = now_utc.astimezone(tz)
    end_h, end_m = map(int, settings.SMS_QUIET_HOURS_END.split(":"))

    # If before 07:00, schedule for 07:00 today. If >= 19:00, schedule for 07:00 tomorrow.
    start_h, start_m = map(int, settings.SMS_QUIET_HOURS_START.split(":"))
    if local_now.time() >= time(start_h, start_m):
        target_date = local_now.date() + timedelta(days=1)
    else:
        target_date = local_now.date()

    target_dt = datetime.combine(target_date, time(end_h, end_m), tzinfo=tz)
    return target_dt.astimezone(UTC)


async def enqueue_sms(
    db: AsyncSession,
    to_e164: str,
    template_key: str,
    params: dict[str, Any],
    body: str,
    dedupe_key: str | None = None,
    related_student_id: uuid.UUID | None = None,
    related_case_id: uuid.UUID | None = None,
) -> SmsOutbox | None:
    if dedupe_key:
        existing = await db.execute(select(SmsOutbox).where(SmsOutbox.dedupe_key == dedupe_key))
        if existing.scalar_one_or_none():
            logger.info("SMS deduplicated and skipped: dedupe_key=%s", dedupe_key)
            return None

    scheduled_at = compute_scheduled_at(template_key)
    outbox_entry = SmsOutbox(
        to_e164=to_e164,
        template_key=template_key,
        params=params,
        body=body,
        dedupe_key=dedupe_key,
        status=SmsStatusEnum.pending,
        scheduled_at=scheduled_at,
        related_student_id=related_student_id,
        related_case_id=related_case_id,
    )
    db.add(outbox_entry)
    return outbox_entry


async def process_outbox_batch(
    db: AsyncSession,
    provider: SmsProvider | None = None,
    batch_size: int = 50,
) -> int:
    if provider is None:
        provider = get_sms_provider()

    now_utc = utc_now()
    query = (
        select(SmsOutbox)
        .where(
            SmsOutbox.status == SmsStatusEnum.pending,
            SmsOutbox.scheduled_at <= now_utc,
        )
        .order_by(SmsOutbox.scheduled_at)
        .limit(batch_size)
    )
    result = await db.execute(query)
    entries = result.scalars().all()

    processed_count = 0
    for entry in entries:
        entry.attempts += 1
        try:
            msg_id = await provider.send_sms(entry.to_e164, entry.body)
            entry.status = SmsStatusEnum.sent
            entry.provider_message_id = msg_id
            entry.sent_at = utc_now()
            entry.last_error = None
            processed_count += 1
        except Exception as e:  # noqa: BLE001
            entry.last_error = str(e)
            if entry.attempts >= 3:
                entry.status = SmsStatusEnum.failed
            logger.error("Failed to dispatch SMS outbox ID %s: %s", entry.id, str(e))

    await db.commit()
    return processed_count
