import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import mask_phone
from app.core.rbac import get_current_user, require_roles
from app.db.session import get_db
from app.models.student import Class, Guardian, Student, StudentStatusEnum, student_guardians
from app.models.user import RoleEnum, User
from app.schemas.student import (
    CSVImportResult,
    GuardianCreate,
    GuardianResponse,
    StudentCreate,
    StudentResponse,
)
from app.services.csv_import import import_students_csv

router = APIRouter(prefix="/students", tags=["students"])


def student_to_response(s: Student) -> StudentResponse:
    guardians_resp: list[GuardianResponse] = []
    if hasattr(s, "guardians") and s.guardians:
        for g in s.guardians:
            guardians_resp.append(
                GuardianResponse(
                    id=g.id,
                    full_name=g.full_name,
                    phone_masked=mask_phone(g.phone_e164),
                    language=g.language,
                    consent_source=g.consent_source,
                    sms_opt_out=g.sms_opt_out,
                )
            )

    return StudentResponse(
        id=s.id,
        school_id=s.school_id,
        class_id=s.class_id,
        class_name=s.class_group.name if s.class_group else None,
        roll_number=s.roll_number,
        full_name=s.full_name,
        student_code=s.student_code,
        sex=s.sex,
        birth_year=s.birth_year,
        is_repeater=s.is_repeater,
        status=s.status,
        enrolled_at=s.enrolled_at,
        guardians=guardians_resp,
    )


@router.get("", response_model=list[StudentResponse], operation_id="list_students")
async def list_students(
    school_id: uuid.UUID | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    q: str | None = Query(None),
    status_filter: StudentStatusEnum | None = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Student)
        .options(selectinload(Student.class_group), selectinload(Student.guardians))
        .order_by(Student.roll_number)
    )

    if current_user.role == RoleEnum.head_teacher:
        query = query.where(Student.school_id == current_user.school_id)
    elif school_id:
        query = query.where(Student.school_id == school_id)

    if class_id:
        query = query.where(Student.class_id == class_id)
    if status_filter:
        query = query.where(Student.status == status_filter)
    if q:
        query = query.where(Student.full_name.ilike(f"%{q.strip()}%"))

    result = await db.execute(query)
    students = result.scalars().all()
    return [student_to_response(s) for s in students]


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED, operation_id="create_student")
async def create_student(
    req: StudentCreate,
    current_user: User = Depends(require_roles(RoleEnum.admin, RoleEnum.head_teacher)),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == RoleEnum.head_teacher and current_user.school_id != req.school_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create students outside your school")

    # Verify class exists
    target_class = await db.get(Class, req.class_id)
    if not target_class or target_class.school_id != req.school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Class not found in this school")

    # Check roll number uniqueness in class
    dup = await db.execute(
        select(Student).where(Student.class_id == req.class_id, Student.roll_number == req.roll_number)
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Roll number {req.roll_number} already in use in this class")

    student = Student(
        school_id=req.school_id,
        class_id=req.class_id,
        roll_number=req.roll_number,
        full_name=req.full_name.strip(),
        student_code=req.student_code.strip() if req.student_code else None,
        sex=req.sex,
        birth_year=req.birth_year,
        is_repeater=req.is_repeater,
        status=StudentStatusEnum.active,
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)

    # Re-fetch with relationships
    res = await db.execute(
        select(Student)
        .options(selectinload(Student.class_group), selectinload(Student.guardians))
        .where(Student.id == student.id)
    )
    return student_to_response(res.scalar_one())


@router.post("/{id}/guardians", response_model=GuardianResponse, operation_id="add_student_guardian")
async def add_student_guardian(
    id: uuid.UUID,
    req: GuardianCreate,
    current_user: User = Depends(require_roles(RoleEnum.admin, RoleEnum.head_teacher)),
    db: AsyncSession = Depends(get_db),
):
    student = await db.get(Student, id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    if current_user.role == RoleEnum.head_teacher and current_user.school_id != student.school_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify student outside your school")

    guard_res = await db.execute(select(Guardian).where(Guardian.phone_e164 == req.phone_e164))
    guardian = guard_res.scalar_one_or_none()
    if not guardian:
        guardian = Guardian(
            full_name=req.full_name.strip(),
            phone_e164=req.phone_e164.strip(),
            language=req.language,
        )
        db.add(guardian)
        await db.flush()

    link_res = await db.execute(
        select(student_guardians).where(
            student_guardians.c.student_id == student.id,
            student_guardians.c.guardian_id == guardian.id,
        )
    )
    if not link_res.first():
        await db.execute(
            student_guardians.insert().values(
                student_id=student.id,
                guardian_id=guardian.id,
                relationship=req.relationship,
                is_primary=req.is_primary,
            )
        )
        await db.commit()

    return GuardianResponse(
        id=guardian.id,
        full_name=guardian.full_name,
        phone_masked=mask_phone(guardian.phone_e164),
        language=guardian.language,
        consent_source=guardian.consent_source,
        sms_opt_out=guardian.sms_opt_out,
    )


@router.post("/import", response_model=CSVImportResult, operation_id="import_students")
async def import_students(
    file: UploadFile = File(...),
    school_id: uuid.UUID | None = Query(None),
    dry_run: bool = Query(False),
    current_user: User = Depends(require_roles(RoleEnum.admin, RoleEnum.head_teacher)),
    db: AsyncSession = Depends(get_db),
):
    target_school_id = current_user.school_id if current_user.role == RoleEnum.head_teacher else school_id
    if not target_school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="school_id is required")

    content_bytes = await file.read()
    try:
        content_str = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content_str = content_bytes.decode("latin-1")

    return await import_students_csv(
        db=db,
        school_id=target_school_id,
        csv_content=content_str,
        dry_run=dry_run,
    )
