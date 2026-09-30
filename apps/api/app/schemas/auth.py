import uuid

from pydantic import BaseModel, EmailStr

from app.models.user import LanguageEnum, RoleEnum


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserMeResponse(BaseModel):
    id: uuid.UUID
    email: str | None = None
    full_name: str
    role: RoleEnum
    language: LanguageEnum
    phone_masked: str | None = None
    school_id: uuid.UUID | None = None
    sector_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    is_active: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserMeResponse
