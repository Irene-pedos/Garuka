import uuid
import re
import base64

import jwt
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import get_current_user, user_to_me_response
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    get_pin_hash,
    verify_password,
    verify_pin,
)
from app.db.session import get_db
from app.models.user import RoleEnum, User
from app.schemas.auth import (
    AvatarUploadResponse,
    ChangePasswordRequest,
    ChangePinRequest,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserMeResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, operation_id="auth_login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # In MVP, teachers and mentors use USSD; dashboard requires password
    if user.role in (RoleEnum.teacher, RoleEnum.mentor) and not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher and mentor access is available via USSD only in MVP",
        )

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    user_data = {"sub": str(user.id), "role": user.role.value}
    access_token = create_access_token(user_data)
    refresh_token = create_refresh_token(user_data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_to_me_response(user),
    )


@router.post("/refresh", response_model=TokenResponse, operation_id="auth_refresh")
async def refresh_token_endpoint(req: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type, refresh token expected",
            )
        user_id = uuid.UUID(payload.get("sub"))
    except (jwt.PyJWTError, ValueError) as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from err

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or not found",
        )

    user_data = {"sub": str(user.id), "role": user.role.value}
    new_access_token = create_access_token(user_data)
    new_refresh_token = create_refresh_token(user_data)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user=user_to_me_response(user),
    )


@router.post("/logout", operation_id="auth_logout")
async def logout(current_user: User = Depends(get_current_user)):
    return {"status": "ok", "message": "Successfully logged out"}


@router.get("/me", response_model=UserMeResponse, operation_id="auth_get_me")
async def get_me(current_user: User = Depends(get_current_user)):
    return user_to_me_response(current_user)


@router.patch("/me", response_model=UserMeResponse, operation_id="auth_update_me")
async def update_me(
    req: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if req.full_name is not None:
        name = req.full_name.strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Full name cannot be empty",
            )
        current_user.full_name = name

    if req.avatar_url is not None:
        current_user.avatar_url = req.avatar_url.strip() or None

    if req.language is not None:
        current_user.language = req.language

    if req.phone_e164 is not None:
        phone = req.phone_e164.strip() or None
        if phone:
            if not re.match(r"^\+[1-9]\d{1,14}$", phone):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Phone number must be in E.164 format (e.g. +250788123456)",
                )
            existing = await db.execute(
                select(User).where(User.phone_e164 == phone, User.id != current_user.id)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This phone number is already registered to another account",
                )
        current_user.phone_e164 = phone

    await db.commit()
    await db.refresh(current_user, ["school", "sector", "district"])
    return user_to_me_response(current_user)


@router.post("/change-password", operation_id="auth_change_password")
async def change_password(
    req: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.password_hash:
        if not verify_password(req.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

    if len(req.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be at least 8 characters long",
        )

    current_user.password_hash = get_password_hash(req.new_password)
    await db.commit()
    return {"status": "ok", "message": "Password updated successfully"}


@router.post("/change-pin", operation_id="auth_change_pin")
async def change_pin(
    req: ChangePinRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.pin_hash:
        if not req.current_pin or not verify_pin(req.current_pin, current_user.pin_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current PIN is incorrect",
            )

    new_pin = req.new_pin.strip()
    if not new_pin.isdigit() or len(new_pin) != 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PIN must be exactly 4 digits",
        )

    current_user.pin_hash = get_pin_hash(new_pin)
    current_user.pin_failed_count = 0
    current_user.pin_locked_until = None
    await db.commit()
    return {"status": "ok", "message": "USSD PIN updated successfully"}


@router.post("/avatar", response_model=AvatarUploadResponse, operation_id="auth_upload_avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image (JPEG, PNG, WebP, GIF, or SVG)",
        )

    contents = await file.read()
    if len(contents) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image size must be less than 2MB",
        )

    encoded = base64.b64encode(contents).decode("utf-8")
    data_uri = f"data:{file.content_type};base64,{encoded}"

    current_user.avatar_url = data_uri
    await db.commit()
    return AvatarUploadResponse(avatar_url=data_uri, message="Avatar updated successfully")
