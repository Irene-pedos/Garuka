import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.case import BarrierCodeEnum, HelpRequestStatusEnum


class HelpRequestCreate(BaseModel):
    student_id: uuid.UUID
    guardian_id: uuid.UUID | None = None
    barrier_code: BarrierCodeEnum
    consent: bool = True


class HelpRequestUpdate(BaseModel):
    status: HelpRequestStatusEnum


class HelpRequestListItem(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    class_name: str | None = None
    school_id: uuid.UUID
    school_name: str
    guardian_id: uuid.UUID
    guardian_name: str
    guardian_phone: str
    barrier_code: BarrierCodeEnum
    status: HelpRequestStatusEnum
    created_at: datetime

    class Config:
        from_attributes = True
