import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import get_current_user, require_roles
from app.db.session import get_db
from app.models.geo import School
from app.models.student import Class
from app.models.user import RoleEnum, User
from app.schemas.student import ClassCreate, ClassResponse, ClassUpdate

router = APIRouter(tags=["classes"])


@router.get("/schools/{school_id}/classes", response_model=list[ClassResponse], operation_id="list_school_classes")
async def list_school_classes(
    school_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == RoleEnum.head_teacher and current_user.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access classes outside your school")

    query = select(Class).where(Class.school_id == school_id).order_by(Class.grade, Class.name)
    result = await db.execute(query)
    return result.scalars().all()


@router.post(
    "/schools/{school_id}/classes",
    response_model=ClassResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_school_class",
)
async def create_school_class(
    school_id: uuid.UUID,
    req: ClassCreate,
    current_user: User = Depends(require_roles(RoleEnum.admin, RoleEnum.head_teacher)),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == RoleEnum.head_teacher and current_user.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create classes outside your school")

    school = await db.get(School, school_id)
    if not school:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")

    new_class = Class(
        school_id=school_id,
        name=req.name.strip(),
        grade=req.grade,
        academic_year=req.academic_year,
        class_teacher_id=req.class_teacher_id,
    )
    db.add(new_class)
    await db.commit()
    await db.refresh(new_class)
    return new_class


@router.patch("/classes/{id}", response_model=ClassResponse, operation_id="update_class")
async def update_class(
    id: uuid.UUID,
    req: ClassUpdate,
    current_user: User = Depends(require_roles(RoleEnum.admin, RoleEnum.head_teacher)),
    db: AsyncSession = Depends(get_db),
):
    c = await db.get(Class, id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    if current_user.role == RoleEnum.head_teacher and current_user.school_id != c.school_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update class outside your school")

    if req.name is not None:
        c.name = req.name.strip()
    if req.grade is not None:
        c.grade = req.grade
    if req.academic_year is not None:
        c.academic_year = req.academic_year
    if req.class_teacher_id is not None:
        c.class_teacher_id = req.class_teacher_id

    await db.commit()
    await db.refresh(c)
    return c
