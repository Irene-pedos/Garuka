import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import mask_phone
from app.core.rbac import get_current_user, require_roles
from app.db.session import get_db
from app.models.attendance import Absence
from app.models.base import utc_now
from app.models.case import (
    Case,
    CaseEvent,
    CaseStatusEnum,
    MentorVisit,
)
from app.models.geo import School, Sector
from app.models.student import Student
from app.models.user import RoleEnum, User
from app.schemas.case import (
    CaseAssignRequest,
    CaseDetail,
    CaseEscalateRequest,
    CaseEventRead,
    CaseListItem,
    CaseMetrics,
    CaseNoteRequest,
    CaseResolveRequest,
    MentorVisitRead,
)
from app.services.case_service import (
    CaseNotFoundError,
    CaseValidationError,
    add_case_note as service_add_case_note,
    assign_case_mentor as service_assign_case_mentor,
    escalate_case as service_escalate_case,
    resolve_case as service_resolve_case,
)
from app.services.rules_engine import calculate_student_metrics

router = APIRouter(prefix="/cases", tags=["cases"])


def check_case_access(user: User, case: Case, school: School | None = None) -> bool:
    if user.role == RoleEnum.admin:
        return True
    if user.role == RoleEnum.district_director:
        return True  # If district filtering is configured or within district
    if user.role == RoleEnum.sector_officer:
        if school and school.sector_id == user.sector_id:
            return True
        return case.sector_officer_id == user.id
    if user.role in {RoleEnum.head_teacher, RoleEnum.teacher}:
        return case.school_id == user.school_id
    if user.role == RoleEnum.mentor:
        return case.mentor_id == user.id
    return False


@router.get("", response_model=list[CaseListItem], operation_id="list_cases")
async def list_cases(
    status_filter: CaseStatusEnum | None = Query(None, alias="status"),
    level: int | None = Query(None),
    school_id: uuid.UUID | None = Query(None),
    sector_id: uuid.UUID | None = Query(None),
    mentor_id: uuid.UUID | None = Query(None),
    q: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CaseListItem]:
    query = (
        select(Case)
        .options(
            selectinload(Case.student).selectinload(Student.class_group),
            selectinload(Case.school).selectinload(School.sector),
            selectinload(Case.mentor),
        )
        .order_by(desc(Case.opened_at))
    )

    # Scoping by role
    if current_user.role == RoleEnum.admin:
        pass
    elif current_user.role == RoleEnum.district_director:
        if current_user.district_id:
            query = query.join(School, Case.school_id == School.id).join(
                Sector, School.sector_id == Sector.id
            ).where(Sector.district_id == current_user.district_id)
    elif current_user.role == RoleEnum.sector_officer:
        if current_user.sector_id:
            query = query.join(School, Case.school_id == School.id).where(
                School.sector_id == current_user.sector_id
            )
        else:
            query = query.where(Case.sector_officer_id == current_user.id)
    elif current_user.role in {RoleEnum.head_teacher, RoleEnum.teacher}:
        if not current_user.school_id:
            return []
        query = query.where(Case.school_id == current_user.school_id)
    elif current_user.role == RoleEnum.mentor:
        query = query.where(Case.mentor_id == current_user.id)
    else:
        return []

    if status_filter:
        query = query.where(Case.status == status_filter)
    if level:
        query = query.where(Case.level == level)
    if school_id:
        query = query.where(Case.school_id == school_id)
    if mentor_id:
        query = query.where(Case.mentor_id == mentor_id)
    if sector_id:
        query = query.join(School, Case.school_id == School.id).where(
            School.sector_id == sector_id
        )

    if q:
        search_term = f"%{q.strip()}%"
        query = query.join(Student, Case.student_id == Student.id).where(
            or_(
                Case.ref.ilike(search_term),
                Student.full_name.ilike(search_term),
            )
        )

    result = await db.execute(query)
    cases = result.scalars().all()

    now = datetime.now(UTC)
    items: list[CaseListItem] = []
    for c in cases:
        # SLA deadline = opened_at + 3 calendar days (approx 3 school days for SLA display)
        sla_deadline = c.opened_at.replace(microsecond=0)
        sla_breached = (
            c.status in {CaseStatusEnum.open, CaseStatusEnum.mentor_assigned}
            and (now - c.opened_at).total_seconds() > (3 * 24 * 3600)
        )

        items.append(
            CaseListItem(
                id=c.id,
                ref=c.ref,
                student_id=c.student_id,
                student_name=c.student.full_name if c.student else "Unknown",
                student_gender=c.student.sex.value if (c.student and c.student.sex) else None,
                class_name=c.student.class_group.name if (c.student and c.student.class_group) else None,
                school_id=c.school_id,
                school_name=c.school.name if c.school else "Unknown School",
                sector_name=c.school.sector.name if (c.school and c.school.sector) else None,
                status=c.status.value,
                level=c.level,
                trigger=c.trigger.value,
                risk_score=c.risk_score,
                mentor_id=c.mentor_id,
                mentor_name=c.mentor.full_name if c.mentor else None,
                opened_at=c.opened_at,
                resolved_at=c.resolved_at,
                sla_deadline=sla_deadline,
                sla_breached=sla_breached,
            )
        )
    return items


@router.get("/{case_id}", response_model=CaseDetail, operation_id="get_case_detail")
async def get_case_detail(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseDetail:
    query = (
        select(Case)
        .options(
            selectinload(Case.student)
            .selectinload(Student.class_group),
            selectinload(Case.student)
            .selectinload(Student.guardians),
            selectinload(Case.school).selectinload(School.sector),
            selectinload(Case.mentor),
            selectinload(Case.events).selectinload(CaseEvent.actor),
            selectinload(Case.visits).selectinload(MentorVisit.mentor),
        )
        .where(Case.id == case_id)
    )
    result = await db.execute(query)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if not check_case_access(current_user, case, case.school):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden to this case",
        )

    # Calculate metrics
    consec, abs_30, abs_term, ret_streak = (0, 0, 0, 0)
    if case.student:
        consec, abs_30, abs_term, ret_streak = await calculate_student_metrics(case.student, db)
    metrics = CaseMetrics(
        consecutive_absences=consec,
        monthly_absences=abs_30,
        term_absences=abs_term,
        return_streak=ret_streak,
    )

    # Attendance heatmap (recent 30 records)
    rec_res = await db.execute(
        select(Absence)
        .where(Absence.student_id == case.student_id)
        .order_by(desc(Absence.date))
        .limit(30)
    )
    records = rec_res.scalars().all()
    absence_heatmap = [
        {
            "date": r.date.isoformat(),
            "status": r.status.value,
            "reason": r.reason_code.value if r.reason_code else None,
            "reason_source": r.reason_source.value if r.reason_source else None,
        }
        for r in records
    ]

    # Parent info
    parent_name = None
    parent_phone = None
    if case.student and case.student.guardians:
        primary_g = case.student.guardians[0]
        parent_name = primary_g.full_name
        parent_phone = mask_phone(primary_g.phone_e164)

    # Visits list
    visits_read: list[MentorVisitRead] = []
    for v in sorted(case.visits, key=lambda x: x.started_at, reverse=True):
        visits_read.append(
            MentorVisitRead(
                id=v.id,
                case_id=v.case_id,
                mentor_id=v.mentor_id,
                mentor_name=v.mentor.full_name if v.mentor else "Unknown",
                started_at=v.started_at,
                verified=v.verified,
                verified_method=v.verified_method.value,
                outcome=v.outcome.value,
                barrier_code=v.barrier_code.value if v.barrier_code else None,
                notes=v.notes,
            )
        )

    # Events timeline
    events_read: list[CaseEventRead] = []
    for ev in sorted(case.events, key=lambda x: x.created_at, reverse=True):
        events_read.append(
            CaseEventRead(
                id=ev.id,
                case_id=ev.case_id,
                type=ev.type,
                actor_name=ev.actor.full_name if ev.actor else None,
                payload=ev.payload or {},
                created_at=ev.created_at,
            )
        )

    now = datetime.now(UTC)
    sla_breached = (
        case.status in {CaseStatusEnum.open, CaseStatusEnum.mentor_assigned}
        and (now - case.opened_at).total_seconds() > (3 * 24 * 3600)
    )

    return CaseDetail(
        id=case.id,
        ref=case.ref,
        student_id=case.student_id,
        student_name=case.student.full_name if case.student else "Unknown",
        student_gender=case.student.sex.value if (case.student and case.student.sex) else None,
        class_name=case.student.class_group.name if (case.student and case.student.class_group) else None,
        school_id=case.school_id,
        school_name=case.school.name if case.school else "Unknown School",
        sector_name=case.school.sector.name if (case.school and case.school.sector) else None,
        status=case.status.value,
        level=case.level,
        trigger=case.trigger.value,
        risk_score=case.risk_score,
        mentor_id=case.mentor_id,
        mentor_name=case.mentor.full_name if case.mentor else None,
        opened_at=case.opened_at,
        resolved_at=case.resolved_at,
        sla_deadline=case.opened_at.replace(microsecond=0),
        sla_breached=sla_breached,
        parent_name=parent_name,
        parent_phone=parent_phone,
        metrics=metrics,
        absence_heatmap=absence_heatmap,
        visits=visits_read,
        events=events_read,
    )


@router.patch("/{case_id}/assign", response_model=CaseDetail, operation_id="assign_case_mentor")
async def assign_case_mentor(
    case_id: uuid.UUID,
    payload: CaseAssignRequest,
    current_user: User = Depends(
        require_roles(RoleEnum.admin, RoleEnum.sector_officer)
    ),
    db: AsyncSession = Depends(get_db),
) -> CaseDetail:
    try:
        await service_assign_case_mentor(
            db=db,
            case_id=case_id,
            mentor_id=payload.mentor_id,
            actor_user_id=current_user.id,
        )
        return await get_case_detail(case_id, current_user, db)
    except CaseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    except CaseValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{case_id}/escalate", response_model=CaseDetail, operation_id="escalate_case")
async def escalate_case(
    case_id: uuid.UUID,
    payload: CaseEscalateRequest,
    current_user: User = Depends(
        require_roles(
            RoleEnum.admin,
            RoleEnum.head_teacher,
            RoleEnum.sector_officer,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> CaseDetail:
    try:
        await service_escalate_case(
            db=db,
            case_id=case_id,
            to_level=payload.to_level,
            note=payload.note,
            actor_user_id=current_user.id,
        )
        return await get_case_detail(case_id, current_user, db)
    except CaseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    except CaseValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{case_id}/notes", response_model=CaseDetail, operation_id="add_case_note")
async def add_case_note(
    case_id: uuid.UUID,
    payload: CaseNoteRequest,
    current_user: User = Depends(
        require_roles(
            RoleEnum.admin,
            RoleEnum.district_director,
            RoleEnum.sector_officer,
            RoleEnum.head_teacher,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> CaseDetail:
    try:
        await service_add_case_note(
            db=db,
            case_id=case_id,
            text=payload.text,
            actor_user_id=current_user.id,
        )
        return await get_case_detail(case_id, current_user, db)
    except CaseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")


@router.post("/{case_id}/resolve", response_model=CaseDetail, operation_id="resolve_case")
async def resolve_case(
    case_id: uuid.UUID,
    payload: CaseResolveRequest,
    current_user: User = Depends(
        require_roles(
            RoleEnum.admin,
            RoleEnum.sector_officer,
            RoleEnum.head_teacher,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> CaseDetail:
    try:
        await service_resolve_case(
            db=db,
            case_id=case_id,
            outcome=payload.outcome,
            note=payload.note,
            actor_user_id=current_user.id,
        )
        return await get_case_detail(case_id, current_user, db)
    except CaseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    except CaseValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
