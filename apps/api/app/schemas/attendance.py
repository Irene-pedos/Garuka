import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.attendance import AbsenceStatusEnum, ReasonCodeEnum, SubmissionSourceEnum


class AttendanceSubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    class_id: uuid.UUID
    date: date
    submitted_by: uuid.UUID
    source: SubmissionSourceEnum
    absent_count: int
    submitted_at: datetime


class StudentAttendanceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    roll_number: int
    full_name: str
    is_absent: bool
    absence_id: uuid.UUID | None = None
    reason_code: ReasonCodeEnum | None = None
    status: AbsenceStatusEnum | None = None


class ClassAttendanceResponse(BaseModel):
    class_id: uuid.UUID
    class_name: str
    date: date
    submission: AttendanceSubmissionResponse | None = None
    students: list[StudentAttendanceItem] = []


class SubmitAttendanceRequest(BaseModel):
    date: date
    absent_student_ids: list[uuid.UUID] = []


class DayCompliance(BaseModel):
    date: date
    status: str  # "submitted" | "missing" | "non_school_day"
    absent_count: int | None = None


class ClassCompliance(BaseModel):
    class_id: uuid.UUID
    class_name: str
    grade: int
    days: list[DayCompliance]


class SchoolComplianceResponse(BaseModel):
    school_id: uuid.UUID
    school_name: str
    from_date: date
    to_date: date
    compliance_pct: float
    classes: list[ClassCompliance]
