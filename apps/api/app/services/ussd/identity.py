import re
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import Guardian
from app.models.user import LanguageEnum, User


class IdentityRole(str, Enum):
    STAFF = "STAFF"
    PARENT = "PARENT"
    ROLE_PICK = "ROLE_PICK"
    UNREGISTERED = "UNREGISTERED"


@dataclass
class USSDIdentity:
    phone_e164: str
    role_type: IdentityRole
    user: User | None = None
    guardian: Guardian | None = None
    language: LanguageEnum = LanguageEnum.rw


def normalize_phone_e164(raw_phone: str) -> str:
    """Normalize phone number to Rwandan E.164 format (+2507XXXXXXXX)."""
    cleaned = re.sub(r"[\s\-\(\)]", "", raw_phone.strip())
    if cleaned.startswith("07") and len(cleaned) == 10:
        return f"+25{cleaned}"
    if cleaned.startswith("7") and len(cleaned) == 9:
        return f"+250{cleaned}"
    if cleaned.startswith("2507") and len(cleaned) == 12:
        return f"+{cleaned}"
    if cleaned.startswith("+2507") and len(cleaned) == 13:
        return cleaned
    return raw_phone.strip()


async def resolve_identity(phone_number: str, db: AsyncSession) -> USSDIdentity:
    normalized = normalize_phone_e164(phone_number)

    # 1. Check staff user
    user_res = await db.execute(
        select(User).where(User.phone_e164 == normalized, User.is_active.is_(True))
    )
    user = user_res.scalar_one_or_none()

    # 2. Check guardian
    guardian_res = await db.execute(select(Guardian).where(Guardian.phone_e164 == normalized))
    guardian = guardian_res.scalar_one_or_none()

    if user and guardian:
        role_type = IdentityRole.ROLE_PICK
        lang = user.language or guardian.language or LanguageEnum.rw
    elif user:
        role_type = IdentityRole.STAFF
        lang = user.language or LanguageEnum.rw
    elif guardian:
        role_type = IdentityRole.PARENT
        lang = guardian.language or LanguageEnum.rw
    else:
        role_type = IdentityRole.UNREGISTERED
        lang = LanguageEnum.rw

    return USSDIdentity(
        phone_e164=normalized,
        role_type=role_type,
        user=user,
        guardian=guardian,
        language=lang,
    )
