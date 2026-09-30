import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.student import Class


class SchoolLevelEnum(str, Enum):
    primary = "primary"
    secondary = "secondary"
    both = "both"


class District(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "districts"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    sectors: Mapped[list["Sector"]] = relationship("Sector", back_populates="district", cascade="all, delete-orphan")


class Sector(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sectors"
    __table_args__ = (
        UniqueConstraint("district_id", "name", name="uq_sector_district_name"),
    )

    district_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("districts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    district: Mapped["District"] = relationship("District", back_populates="sectors")
    schools: Mapped[list["School"]] = relationship("School", back_populates="sector", cascade="all, delete-orphan")


class School(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "schools"
    __table_args__ = (
        UniqueConstraint("sector_id", "name", name="uq_school_sector_name"),
    )

    sector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sectors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    level: Mapped[SchoolLevelEnum] = mapped_column(
        SQLEnum(SchoolLevelEnum, name="school_level_enum"),
        default=SchoolLevelEnum.primary,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sector: Mapped["Sector"] = relationship("Sector", back_populates="schools")
    classes: Mapped[list["Class"]] = relationship("Class", back_populates="school", cascade="all, delete-orphan")
