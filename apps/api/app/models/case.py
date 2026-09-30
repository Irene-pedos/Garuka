import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, utc_now


class CaseStatusEnum(str, Enum):
    open = "open"
    mentor_assigned = "mentor_assigned"
    visited = "visited"
    escalated_sector = "escalated_sector"
    escalated_district = "escalated_district"
    resolved_returned = "resolved_returned"
    closed_moved = "closed_moved"
    closed_other = "closed_other"


class CaseTriggerEnum(str, Enum):
    consecutive = "consecutive"
    monthly = "monthly"
    term_total = "term_total"
    manual = "manual"


class VerifiedMethodEnum(str, Enum):
    parent_code = "parent_code"
    unverified = "unverified"


class VisitOutcomeEnum(str, Enum):
    will_return = "will_return"
    plan_agreed = "plan_agreed"
    needs_sector_help = "needs_sector_help"
    moved_away = "moved_away"


class BarrierCodeEnum(str, Enum):
    COST = "COST"
    HUNGER = "HUNGER"
    HEALTH = "HEALTH"
    DISTANCE = "DISTANCE"
    FAMILY = "FAMILY"
    OTHER = "OTHER"


class HelpRequestStatusEnum(str, Enum):
    new = "new"
    seen = "seen"
    in_progress = "in_progress"
    closed = "closed"


class Case(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_status_school", "status", "school_id"),
        Index("ix_cases_mentor_id", "mentor_id"),
    )

    ref: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[CaseStatusEnum] = mapped_column(
        SQLEnum(CaseStatusEnum, name="case_status_enum"),
        default=CaseStatusEnum.open,
        nullable=False,
        index=True,
    )
    level: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    trigger: Mapped[CaseTriggerEnum] = mapped_column(
        SQLEnum(CaseTriggerEnum, name="case_trigger_enum"),
        nullable=False,
    )
    risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mentor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    sector_officer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    reopened_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    events: Mapped[list["CaseEvent"]] = relationship("CaseEvent", back_populates="case", cascade="all, delete-orphan")
    visits: Mapped[list["MentorVisit"]] = relationship("MentorVisit", back_populates="case", cascade="all, delete-orphan")


class CaseEvent(Base, UUIDMixin):
    __tablename__ = "case_events"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    case: Mapped["Case"] = relationship("Case", back_populates="events")


class MentorVisit(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "mentor_visits"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mentor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_method: Mapped[VerifiedMethodEnum] = mapped_column(
        SQLEnum(VerifiedMethodEnum, name="verified_method_enum"),
        default=VerifiedMethodEnum.unverified,
        nullable=False,
    )
    outcome: Mapped[VisitOutcomeEnum] = mapped_column(
        SQLEnum(VisitOutcomeEnum, name="visit_outcome_enum"),
        nullable=False,
    )
    barrier_code: Mapped[BarrierCodeEnum | None] = mapped_column(
        SQLEnum(BarrierCodeEnum, name="barrier_code_enum"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped["Case"] = relationship("Case", back_populates="visits")


class VisitCode(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "visit_codes"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mentor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HelpRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "help_requests"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    guardian_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guardians.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    barrier_code: Mapped[BarrierCodeEnum] = mapped_column(
        SQLEnum(BarrierCodeEnum, name="barrier_code_enum", create_constraint=False),
        nullable=False,
    )
    status: Mapped[HelpRequestStatusEnum] = mapped_column(
        SQLEnum(HelpRequestStatusEnum, name="help_request_status_enum"),
        default=HelpRequestStatusEnum.new,
        nullable=False,
        index=True,
    )
