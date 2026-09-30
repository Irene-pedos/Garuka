import uuid

from pydantic import BaseModel


class MentorRead(BaseModel):
    id: uuid.UUID
    name: str
    email: str | None = None
    phone_e164: str
    sector_id: uuid.UUID | None = None
    sector_name: str | None = None
    active_cases: int = 0
    visits_30d: int = 0
    verified_rate: float = 0.0
    is_active: bool = True

    class Config:
        from_attributes = True
