import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.geo import District, School, Sector


class RoleEnum(str, Enum):
    admin = "admin"
    district_director = "district_director"
    sector_officer = "sector_officer"
    head_teacher = "head_teacher"
    teacher = "teacher"
    mentor = "mentor"


class LanguageEnum(str, Enum):
    rw = "rw"
    en = "en"
    fr = "fr"


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    role: Mapped[RoleEnum] = mapped_column(
        SQLEnum(RoleEnum, name="user_role_enum"),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    phone_e164: Mapped[str | None] = mapped_column(
        String(20), unique=True, nullable=True, index=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pin_failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pin_locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    language: Mapped[LanguageEnum] = mapped_column(
        SQLEnum(LanguageEnum, name="user_language_enum"),
        default=LanguageEnum.rw,
        nullable=False,
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sector_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sectors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("districts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    school: Mapped["School | None"] = relationship("School")
    sector: Mapped["Sector | None"] = relationship("Sector")
    district: Mapped["District | None"] = relationship("District")
