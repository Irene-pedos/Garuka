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
    avatar_url: str | None = None
    role: RoleEnum
    language: LanguageEnum
    phone_masked: str | None = None
    phone_e164: str | None = None
    school_id: uuid.UUID | None = None
    sector_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    school_name: str | None = None
    sector_name: str | None = None
    district_name: str | None = None
    is_active: bool

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None
    language: LanguageEnum | None = None
    phone_e164: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ChangePinRequest(BaseModel):
    current_pin: str | None = None
    new_pin: str


class AvatarUploadResponse(BaseModel):
    avatar_url: str
    message: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserMeResponse
