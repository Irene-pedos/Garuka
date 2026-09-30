import uuid

from pydantic import BaseModel

from app.models.geo import SchoolLevelEnum


class DistrictCreate(BaseModel):
    name: str


class DistrictResponse(BaseModel):
    id: uuid.UUID
    name: str

    class Config:
        from_attributes = True


class SectorCreate(BaseModel):
    district_id: uuid.UUID
    name: str


class SectorResponse(BaseModel):
    id: uuid.UUID
    district_id: uuid.UUID
    name: str

    class Config:
        from_attributes = True


class SchoolCreate(BaseModel):
    sector_id: uuid.UUID
    name: str
    code: str | None = None
    level: SchoolLevelEnum = SchoolLevelEnum.primary


class SchoolUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    level: SchoolLevelEnum | None = None
    is_active: bool | None = None


class SchoolResponse(BaseModel):
    id: uuid.UUID
    sector_id: uuid.UUID
    name: str
    code: str | None = None
    level: SchoolLevelEnum
    is_active: bool

    class Config:
        from_attributes = True
