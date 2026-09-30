import uuid
from datetime import date, datetime
from enum import Enum
from typing import Optional
from sqlalchemy import (
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDMixin, utc_now


class SubmissionSourceEnum(str, Enum):
    ussd = "ussd"
    dashboard = "dashboard"


class AbsenceStatusEnum(str, Enum):
    active = "active"
    voided = "voided"


class ReasonCodeEnum(str, Enum):
    SICK = "SICK"
    WORK = "WORK"
    COST = "COST"
    DISTANCE = "DISTANCE"
    OTHER = "OTHER"


class ReasonSourceEnum(str, Enum):
    parent = "parent"
    teacher = "teacher"
    mentor = "mentor"


class AttendanceSubmission(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "attendance_submissions"
    __table_args__ = (
        UniqueConstraint("class_id", "date", name="uq_attendance_submission_class_date"),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source: Mapped[SubmissionSourceEnum] = mapped_column(
        SQLEnum(SubmissionSourceEnum, name="submission_source_enum"),
        default=SubmissionSourceEnum.ussd,
        nullable=False,
    )
    absent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    absences: Mapped[list["Absence"]] = relationship("Absence", back_populates="submission", cascade="all, delete-orphan")


class Absence(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "absences"
    __table_args__ = (
        UniqueConstraint("student_id", "date", name="uq_absence_student_date"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attendance_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[AbsenceStatusEnum] = mapped_column(
        SQLEnum(AbsenceStatusEnum, name="absence_status_enum"),
        default=AbsenceStatusEnum.active,
        nullable=False,
        index=True,
    )
    reason_code: Mapped[Optional[ReasonCodeEnum]] = mapped_column(
        SQLEnum(ReasonCodeEnum, name="absence_reason_code_enum"),
        nullable=True,
        index=True,
    )
    reason_source: Mapped[Optional[ReasonSourceEnum]] = mapped_column(
        SQLEnum(ReasonSourceEnum, name="absence_reason_source_enum"),
        nullable=True,
    )
    reason_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    submission: Mapped["AttendanceSubmission"] = relationship("AttendanceSubmission", back_populates="absences")
