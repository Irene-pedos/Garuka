import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import mask_phone
from app.core.rbac import get_current_user, require_roles
from app.db.session import get_db
from app.models.base import utc_now
from app.models.case import BarrierCodeEnum, HelpRequest, HelpRequestStatusEnum
from app.models.geo import School
from app.models.student import ConsentSourceEnum, Guardian, Student, student_guardians
from app.models.user import RoleEnum, User
from app.schemas.help_request import (
    HelpRequestCreate,
    HelpRequestListItem,
    HelpRequestUpdate,
)

router = APIRouter(prefix="/help-requests", tags=["help-requests"])


@router.get("", response_model=list[HelpRequestListItem], operation_id="list_help_requests")
async def list_help_requests(
    status_filter: HelpRequestStatusEnum | None = Query(None, alias="status"),
    school_id: uuid.UUID | None = Query(None),
    barrier_code: BarrierCodeEnum | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            RoleEnum.admin,
            RoleEnum.district_director,
            RoleEnum.sector_officer,
            RoleEnum.head_teacher,
            RoleEnum.teacher,
        )
    ),
):
    query = (
        select(HelpRequest)
        .options(
            selectinload(HelpRequest.student).selectinload(Student.school),
            selectinload(HelpRequest.student).selectinload(Student.class_group),
            selectinload(HelpRequest.guardian),
        )
        .order_by(desc(HelpRequest.created_at))
    )

    # Role-based scoping
    if current_user.role in {RoleEnum.head_teacher, RoleEnum.teacher}:
        query = query.join(HelpRequest.student).where(Student.school_id == current_user.school_id)
    elif current_user.role == RoleEnum.sector_officer:
        query = (
            query.join(HelpRequest.student)
            .join(Student.school)
            .where(School.sector_id == current_user.sector_id)
        )
    elif current_user.role == RoleEnum.district_director:
        query = (
            query.join(HelpRequest.student)
            .join(Student.school)
            .join(School.sector)
            .where(School.sector.has(district_id=current_user.district_id))
        )

    if status_filter:
        query = query.where(HelpRequest.status == status_filter)
    if school_id:
        query = query.where(HelpRequest.student.has(school_id=school_id))
    if barrier_code:
        query = query.where(HelpRequest.barrier_code == barrier_code)

    result = await db.execute(query)
    items = result.scalars().all()

    response: list[HelpRequestListItem] = []
    is_admin = current_user.role == RoleEnum.admin

    for hr in items:
        student = hr.student
        guardian = hr.guardian
        school = student.school if student else None
        cls = student.class_group if student else None

        raw_phone = guardian.phone_e164 if guardian else ""
        phone = raw_phone if is_admin else mask_phone(raw_phone)

        response.append(
            HelpRequestListItem(
                id=hr.id,
                student_id=hr.student_id,
                student_name=student.full_name if student else "Unknown",
                class_name=cls.name if cls else None,
                school_id=school.id if school else uuid.UUID(int=0),
                school_name=school.name if school else "Unknown",
                guardian_id=hr.guardian_id,
                guardian_name=guardian.full_name if guardian else "Unknown",
                guardian_phone=phone,
                barrier_code=hr.barrier_code,
                status=hr.status,
                created_at=hr.created_at,
            )
        )

    return response


@router.post("", response_model=HelpRequestListItem, status_code=status.HTTP_201_CREATED, operation_id="create_help_request")
async def create_help_request(
    payload: HelpRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify student exists
    st_res = await db.execute(
        select(Student)
        .options(
            selectinload(Student.school),
            selectinload(Student.class_group),
            selectinload(Student.guardians),
        )
        .where(Student.id == payload.student_id)
    )
    student = st_res.scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {payload.student_id} not found",
        )

    # Determine guardian
    guardian_id = payload.guardian_id
    if not guardian_id:
        # Fall back to primary guardian of the student
        link_res = await db.execute(
            select(student_guardians.c.guardian_id).where(
                student_guardians.c.student_id == student.id,
                student_guardians.c.is_primary.is_(True),
            )
        )
        guardian_id = link_res.scalar_one_or_none()
        if not guardian_id and student.guardians:
            guardian_id = student.guardians[0].id

    if not guardian_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student has no registered guardian.",
        )

    # Guardian-child authorization check: verify guardian is linked to student
    auth_check = await db.execute(
        select(student_guardians).where(
            student_guardians.c.student_id == student.id,
            student_guardians.c.guardian_id == guardian_id,
        )
    )
    if not auth_check.first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guardian is not authorized for this student.",
        )

    # Fetch guardian
    guard_res = await db.execute(select(Guardian).where(Guardian.id == guardian_id))
    guardian = guard_res.scalar_one_or_none()
    if not guardian:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guardian record not found.",
        )

    # Record consent if provided and not previously recorded
    if payload.consent and guardian.consent_at is None:
        guardian.consent_at = utc_now()
        guardian.consent_source = ConsentSourceEnum.dashboard

    # Create help request
    help_req = HelpRequest(
        student_id=student.id,
        guardian_id=guardian.id,
        barrier_code=payload.barrier_code,
        status=HelpRequestStatusEnum.new,
    )
    db.add(help_req)
    await db.commit()
    await db.refresh(help_req)

    is_admin = current_user.role == RoleEnum.admin
    phone = guardian.phone_e164 if is_admin else mask_phone(guardian.phone_e164)

    return HelpRequestListItem(
        id=help_req.id,
        student_id=student.id,
        student_name=student.full_name,
        class_name=student.class_group.name if student.class_group else None,
        school_id=student.school.id if student.school else uuid.UUID(int=0),
        school_name=student.school.name if student.school else "Unknown",
        guardian_id=guardian.id,
        guardian_name=guardian.full_name,
        guardian_phone=phone,
        barrier_code=help_req.barrier_code,
        status=help_req.status,
        created_at=help_req.created_at,
    )


@router.patch("/{id}", response_model=HelpRequestListItem, operation_id="update_help_request_status")
async def update_help_request_status(
    id: uuid.UUID,
    payload: HelpRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            RoleEnum.admin,
            RoleEnum.district_director,
            RoleEnum.sector_officer,
            RoleEnum.head_teacher,
        )
    ),
):
    query = (
        select(HelpRequest)
        .options(
            selectinload(HelpRequest.student).selectinload(Student.school),
            selectinload(HelpRequest.student).selectinload(Student.class_group),
            selectinload(HelpRequest.guardian),
        )
        .where(HelpRequest.id == id)
    )
    res = await db.execute(query)
    help_req = res.scalar_one_or_none()
    if not help_req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Help request {id} not found",
        )

    # Scoping check on update
    student = help_req.student
    if current_user.role == RoleEnum.head_teacher:
        if not student or student.school_id != current_user.school_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif current_user.role == RoleEnum.sector_officer:
        if not student or not student.school or student.school.sector_id != current_user.sector_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    help_req.status = payload.status
    await db.commit()
    await db.refresh(help_req)

    guardian = help_req.guardian
    school = student.school if student else None
    cls = student.class_group if student else None
    is_admin = current_user.role == RoleEnum.admin
    phone = guardian.phone_e164 if (guardian and is_admin) else mask_phone(guardian.phone_e164 if guardian else "")

    return HelpRequestListItem(
        id=help_req.id,
        student_id=help_req.student_id,
        student_name=student.full_name if student else "Unknown",
        class_name=cls.name if cls else None,
        school_id=school.id if school else uuid.UUID(int=0),
        school_name=school.name if school else "Unknown",
        guardian_id=help_req.guardian_id,
        guardian_name=guardian.full_name if guardian else "Unknown",
        guardian_phone=phone,
        barrier_code=help_req.barrier_code,
        status=help_req.status,
        created_at=help_req.created_at,
    )
