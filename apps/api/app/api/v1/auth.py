import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import get_current_user, user_to_me_response
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.db.session import get_db
from app.models.user import RoleEnum, User
from app.schemas.auth import LoginRequest, RefreshTokenRequest, TokenResponse, UserMeResponse

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
