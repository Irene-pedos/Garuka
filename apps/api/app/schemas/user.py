import uuid

from pydantic import BaseModel, EmailStr

from app.models.user import LanguageEnum, RoleEnum


class UserAssignedClassResponse(BaseModel):
    id: uuid.UUID
    name: str
    grade: int
    academic_year: int | None = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr | None = None
    phone_e164: str | None = None
    role: RoleEnum
    password: str | None = None
    language: LanguageEnum = LanguageEnum.rw
    school_id: uuid.UUID | None = None
    sector_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    class_ids: list[uuid.UUID] | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone_e164: str | None = None
    language: LanguageEnum | None = None
    is_active: bool | None = None
    school_id: uuid.UUID | None = None
    sector_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    class_ids: list[uuid.UUID] | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None = None
    phone_masked: str | None = None
    role: RoleEnum
    language: LanguageEnum
    school_id: uuid.UUID | None = None
    sector_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    is_active: bool
    assigned_classes: list[UserAssignedClassResponse] = []

    class Config:
        from_attributes = True


class ResetPinResponse(BaseModel):
    id: uuid.UUID
    message: str
