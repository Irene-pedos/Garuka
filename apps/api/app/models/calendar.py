from datetime import date
from sqlalchemy import Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDMixin


class Term(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "terms"
    __table_args__ = (
        UniqueConstraint("academic_year", "term_no", name="uq_term_year_no"),
    )

    academic_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    term_no: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)


class Holiday(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "holidays"

    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
