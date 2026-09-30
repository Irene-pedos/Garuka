import uuid
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.user import LanguageEnum

if TYPE_CHECKING:
    from app.models.geo import School

# Many-to-many relationship between classes and teachers
class_teachers = Table(
    "class_teachers",
    Base.metadata,
    Column("class_id", UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

# Many-to-many relationship between students and guardians
student_guardians = Table(
    "student_guardians",
    Base.metadata,
    Column("student_id", UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
    Column("guardian_id", UUID(as_uuid=True), ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True),
    Column("relationship", String(50), nullable=True),
    Column("is_primary", Boolean, default=False, nullable=False),
)


class ConsentSourceEnum(str, Enum):
    school_form = "school_form"
    ussd = "ussd"
    dashboard = "dashboard"


class StudentStatusEnum(str, Enum):
    active = "active"
    transferred = "transferred"
    dropped_out = "dropped_out"
    graduated = "graduated"


class SexEnum(str, Enum):
    F = "F"
    M = "M"


class Guardian(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "guardians"

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone_e164: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    language: Mapped[LanguageEnum] = mapped_column(
        SQLEnum(LanguageEnum, name="guardian_language_enum"),
        default=LanguageEnum.rw,
        nullable=False,
    )
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_source: Mapped[ConsentSourceEnum | None] = mapped_column(
        SQLEnum(ConsentSourceEnum, name="consent_source_enum"),
        nullable=True,
    )
    sms_opt_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    students: Mapped[list["Student"]] = relationship(
        "Student",
        secondary=student_guardians,
        back_populates="guardians",
    )


class Class(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("school_id", "name", "academic_year", name="uq_class_school_name_year"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False)
    class_teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    school: Mapped["School"] = relationship("School", back_populates="classes")
    students: Mapped[list["Student"]] = relationship("Student", back_populates="class_group", cascade="all, delete-orphan")


class Student(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("class_id", "roll_number", name="uq_student_class_roll"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    roll_number: Mapped[int] = mapped_column(Integer, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    sex: Mapped[SexEnum | None] = mapped_column(SQLEnum(SexEnum, name="student_sex_enum"), nullable=True)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_repeater: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[StudentStatusEnum] = mapped_column(
        SQLEnum(StudentStatusEnum, name="student_status_enum"),
        default=StudentStatusEnum.active,
        nullable=False,
        index=True,
    )
    enrolled_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)

    class_group: Mapped["Class"] = relationship("Class", back_populates="students")
    guardians: Mapped[list["Guardian"]] = relationship(
        "Guardian",
        secondary=student_guardians,
        back_populates="students",
    )
