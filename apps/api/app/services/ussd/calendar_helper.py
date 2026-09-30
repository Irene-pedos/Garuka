from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.calendar import Holiday, Term


def get_kigali_today() -> date:
    tz = ZoneInfo(settings.APP_TZ)
    return datetime.now(tz).date()


async def is_school_day(check_date: date, db: AsyncSession) -> bool:
    # 1. Must be Monday to Friday (0 = Monday, 4 = Friday)
    if check_date.weekday() > 4:
        return False

    # 2. Must not be a holiday
    hol_res = await db.execute(select(Holiday).where(Holiday.date == check_date))
    if hol_res.scalar_one_or_none():
        return False

    # 3. Must be inside an active term
    term_res = await db.execute(
        select(Term).where(Term.start_date <= check_date, Term.end_date >= check_date)
    )
    return term_res.scalar_one_or_none() is not None


async def get_available_attendance_dates(
    db: AsyncSession,
    max_backdate_days: int = 2,
) -> list[date]:
    """
    Returns valid school days for attendance recording, up to max_backdate_days back.
    e.g. [today, previous_school_day].
    """
    today = get_kigali_today()
    valid_dates: list[date] = []

    # Check today
    if await is_school_day(today, db):
        valid_dates.append(today)

    # Search backwards for prior school days
    cursor = today - timedelta(days=1)
    searched = 0
    while len(valid_dates) < (max_backdate_days + 1) and searched < 14:
        if await is_school_day(cursor, db):
            valid_dates.append(cursor)
        cursor -= timedelta(days=1)
        searched += 1

    return valid_dates
