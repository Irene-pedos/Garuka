import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class ScopeInfo(BaseModel):
    level: str
    name: str


class OverviewKPIs(BaseModel):
    students_active: int = 0
    absent_today: int = 0
    open_cases: int = 0
    new_cases_7d: int = 0
    visits_overdue: int = 0
    returned_30d: int = 0
    attendance_compliance_pct: float = 0.0
    classes_missing_today: int = 0
    recent_escalations_count: int = 0
    pending_help_requests_count: int = 0
    mentor_cases_active: int = 0


class ActiveTermInfo(BaseModel):
    academic_year: int
    term_no: int
    name: str


class OverdueCaseItem(BaseModel):
    id: uuid.UUID
    ref: str
    student_name: str
    school_name: str
    level: int
    opened_at: datetime
    days_open: int


class ReportingGapItem(BaseModel):
    class_name: str
    school_name: str
    missing_dates: list[str] = Field(default_factory=list)


class RecentEscalationItem(BaseModel):
    id: uuid.UUID
    ref: str
    student_name: str
    school_name: str
    level: int
    status: str
    escalated_at: datetime


class PendingHelpRequestItem(BaseModel):
    id: uuid.UUID
    student_name: str
    school_name: str
    barrier_code: str
    status: str
    created_at: datetime


class MissingClassItem(BaseModel):
    class_id: uuid.UUID
    class_name: str
    school_name: str


class DailyAttendanceTrendItem(BaseModel):
    date: str
    present: int
    absent: int
    enrolled: int
    cases: int = 0


class AnalyticsOverviewResponse(BaseModel):
    as_of: datetime
    timezone: str = "Africa/Kigali (UTC+2)"
    kigali_today: str
    scope: ScopeInfo
    kpis: OverviewKPIs
    cases_by_level: dict[str, int] = Field(default_factory=dict)
    active_term: ActiveTermInfo | None = None
    overdue_cases: list[OverdueCaseItem] = Field(default_factory=list)
    reporting_gaps: list[ReportingGapItem] = Field(default_factory=list)
    classes_missing_today: list[MissingClassItem] = Field(default_factory=list)
    recent_escalations: list[RecentEscalationItem] = Field(default_factory=list)
    pending_help_requests: list[PendingHelpRequestItem] = Field(default_factory=list)
    attendance_trend: list[DailyAttendanceTrendItem] = Field(default_factory=list)


class SchoolCompareItem(BaseModel):
    school_id: uuid.UUID
    school_name: str
    sector_name: str
    students_active: int = 0
    absent_today: int = 0
    absence_rate_pct: float = 0.0
    open_cases: int = 0
    returned_30d: int = 0
    attendance_compliance_pct: float = 0.0
