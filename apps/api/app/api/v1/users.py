import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import mask_phone
from app.core.rbac import require_roles
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.user import RoleEnum, User
from app.schemas.user import ResetPinResponse, UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def user_to_response(u: User) -> UserResponse:
    return UserResponse(
        id=u.id,
        full_name=u.full_name,
        email=u.email,
        phone_masked=mask_phone(u.phone_e164) if u.phone_e164 else None,
        role=u.role,
        language=u.language,
        school_id=u.school_id,
        sector_id=u.sector_id,
        district_id=u.district_id,
        is_active=u.is_active,
    )


@router.get("", response_model=list[UserResponse], operation_id="list_users")
async def list_users(
    role: RoleEnum | None = Query(None),
    school_id: uuid.UUID | None = Query(None),
    sector_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(require_roles(RoleEnum.admin, RoleEnum.sector_officer, RoleEnum.head_teacher)),
    db: AsyncSession = Depends(get_db),
):
    query = select(User).order_by(User.full_name)

    if current_user.role == RoleEnum.admin:
        if role:
            query = query.where(User.role == role)
        if school_id:
            query = query.where(User.school_id == school_id)
        if sector_id:
            query = query.where(User.sector_id == sector_id)
    elif current_user.role == RoleEnum.sector_officer:
        # Sector officers only manage mentors in their sector
        query = query.where(User.role == RoleEnum.mentor, User.sector_id == current_user.sector_id)
    elif current_user.role == RoleEnum.head_teacher:
        # Head teachers only manage teachers in their school
        query = query.where(User.role == RoleEnum.teacher, User.school_id == current_user.school_id)

    result = await db.execute(query)
    return [user_to_response(u) for u in result.scalars().all()]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED, operation_id="create_user")
async def create_user(
    req: UserCreate,
    current_user: User = Depends(require_roles(RoleEnum.admin, RoleEnum.sector_officer, RoleEnum.head_teacher)),
    db: AsyncSession = Depends(get_db),
):
    # Enforce role scoping for creation
    if current_user.role == RoleEnum.sector_officer:
        if req.role != RoleEnum.mentor:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sector officers can only create mentors")
        req.sector_id = current_user.sector_id
    elif current_user.role == RoleEnum.head_teacher:
        if req.role != RoleEnum.teacher:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Head teachers can only create teachers")
        req.school_id = current_user.school_id

    # Check email / phone uniqueness if provided
    if req.email:
        existing = await db.execute(select(User).where(User.email == req.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    if req.phone_e164:
        existing = await db.execute(select(User).where(User.phone_e164 == req.phone_e164))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone number already registered")

    user = User(
        full_name=req.full_name.strip(),
        email=req.email,
        phone_e164=req.phone_e164,
        role=req.role,
        password_hash=get_password_hash(req.password) if req.password else None,
        pin_hash=None,  # Spec: user creates PIN on first USSD dial
        language=req.language,
        school_id=req.school_id,
        sector_id=req.sector_id,
        district_id=req.district_id,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user_to_response(user)


@router.post("/{id}/reset-pin", response_model=ResetPinResponse, operation_id="reset_user_pin")
async def reset_user_pin(
    id: uuid.UUID,
    current_user: User = Depends(require_roles(RoleEnum.admin, RoleEnum.sector_officer, RoleEnum.head_teacher)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Scope validation
    if current_user.role == RoleEnum.sector_officer and (user.role != RoleEnum.mentor or user.sector_id != current_user.sector_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot reset PIN for user outside your sector")
    if current_user.role == RoleEnum.head_teacher and (user.role != RoleEnum.teacher or user.school_id != current_user.school_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot reset PIN for user outside your school")

    user.pin_hash = None
    user.pin_failed_count = 0
    user.pin_locked_until = None
    await db.commit()

    return ResetPinResponse(id=user.id, message="PIN reset successfully. User will create a new PIN on next USSD dial.")


@router.patch("/{id}", response_model=UserResponse, operation_id="update_user")
async def update_user(
    id: uuid.UUID,
    req: UserUpdate,
    current_user: User = Depends(require_roles(RoleEnum.admin, RoleEnum.sector_officer, RoleEnum.head_teacher)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Scope validation
    if current_user.role == RoleEnum.sector_officer and (user.role != RoleEnum.mentor or user.sector_id != current_user.sector_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify user outside your sector")
    if current_user.role == RoleEnum.head_teacher and (user.role != RoleEnum.teacher or user.school_id != current_user.school_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify user outside your school")

    if req.full_name is not None:
        user.full_name = req.full_name.strip()
    if req.email is not None:
        user.email = req.email
    if req.phone_e164 is not None:
        user.phone_e164 = req.phone_e164
    if req.language is not None:
        user.language = req.language
    if req.is_active is not None:
        user.is_active = req.is_active

    await db.commit()
    await db.refresh(user)
    return user_to_response(user)
