import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CaseEventRead(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    type: str
    actor_name: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class MentorVisitRead(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    mentor_id: uuid.UUID
    mentor_name: str | None = None
    started_at: datetime
    verified: bool
    verified_method: str
    outcome: str
    barrier_code: str | None = None
    notes: str | None = None

    class Config:
        from_attributes = True


class CaseMetrics(BaseModel):
    consecutive_absences: int = 0
    monthly_absences: int = 0
    term_absences: int = 0
    return_streak: int = 0


class CaseListItem(BaseModel):
    id: uuid.UUID
    ref: str
    student_id: uuid.UUID
    student_name: str
    student_gender: str | None = None
    class_name: str | None = None
    school_id: uuid.UUID
    school_name: str
    sector_name: str | None = None
    status: str
    level: int
    trigger: str
    risk_score: int
    mentor_id: uuid.UUID | None = None
    mentor_name: str | None = None
    opened_at: datetime
    resolved_at: datetime | None = None
    sla_deadline: datetime | None = None
    sla_breached: bool = False

    class Config:
        from_attributes = True


class CaseDetail(CaseListItem):
    parent_name: str | None = None
    parent_phone: str | None = None
    metrics: CaseMetrics = Field(default_factory=CaseMetrics)
    absence_heatmap: list[dict[str, Any]] = Field(default_factory=list)
    visits: list[MentorVisitRead] = Field(default_factory=list)
    events: list[CaseEventRead] = Field(default_factory=list)


class CaseAssignRequest(BaseModel):
    mentor_id: uuid.UUID


class CaseEscalateRequest(BaseModel):
    to_level: int = Field(ge=2, le=3)
    note: str | None = None


class CaseNoteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class CaseResolveRequest(BaseModel):
    outcome: str
    note: str | None = None
