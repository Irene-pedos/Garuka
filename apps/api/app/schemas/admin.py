import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.messaging import SmsStatusEnum


class AppSettingsRead(BaseModel):
    rule_consecutive_days: int
    rule_monthly_absences: int
    rule_escalate_term_absences: int
    rule_visit_sla_school_days: int
    rule_return_streak_school_days: int
    rule_district_escalation_days: int
    mentor_max_active_cases: int
    sms_quiet_hours_start: str
    sms_quiet_hours_end: str
    updated_at: datetime | None = None


class AppSettingsUpdate(BaseModel):
    rule_consecutive_days: int | None = Field(None, ge=1, le=30)
    rule_monthly_absences: int | None = Field(None, ge=1, le=50)
    rule_escalate_term_absences: int | None = Field(None, ge=1, le=100)
    rule_visit_sla_school_days: int | None = Field(None, ge=1, le=30)
    rule_return_streak_school_days: int | None = Field(None, ge=1, le=60)
    rule_district_escalation_days: int | None = Field(None, ge=1, le=90)
    mentor_max_active_cases: int | None = Field(None, ge=1, le=100)
    sms_quiet_hours_start: str | None = None
    sms_quiet_hours_end: str | None = None


class SmsOutboxListItem(BaseModel):
    id: uuid.UUID
    to_e164: str
    template_key: str
    body: str
    status: SmsStatusEnum
    attempts: int
    last_error: str | None = None
    scheduled_at: datetime
    sent_at: datetime | None = None

    class Config:
        from_attributes = True


class AuditLogListItem(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    actor_role: str
    action: str
    entity_type: str
    entity_id: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True
