import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.rbac import get_current_user, require_roles
from app.db.session import get_db
from app.models.attendance import Absence, AbsenceStatusEnum, AttendanceSubmission
from app.models.base import utc_now
from app.models.calendar import Term
from app.models.case import Case, CaseStatusEnum, HelpRequest, HelpRequestStatusEnum
from app.models.geo import School, Sector
from app.models.student import Class, Student, StudentStatusEnum
from app.models.user import RoleEnum, User
from app.schemas.analytics import (
    ActiveTermInfo,
    AnalyticsOverviewResponse,
    DailyAttendanceTrendItem,
    MissingClassItem,
    OverdueCaseItem,
    OverviewKPIs,
    PendingHelpRequestItem,
    RecentEscalationItem,
    ReportingGapItem,
    SchoolCompareItem,
    ScopeInfo,
)
from app.services.ussd.calendar_helper import (
    get_available_attendance_dates,
    get_kigali_today,
    is_school_day,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


async def compute_attendance_trend(
    db: AsyncSession,
    current_user: User,
    scoped_class_ids: list[uuid.UUID],
    days: int = 90,
) -> list[DailyAttendanceTrendItem]:
    today = get_kigali_today()
    start_trend_date = today - timedelta(days=days)

    if not scoped_class_ids:
        return []

    # Get active student count per class for scoped classes
    st_count_res = await db.execute(
        select(Student.class_id, func.count(Student.id))
        .where(
            Student.class_id.in_(scoped_class_ids),
            Student.status == StudentStatusEnum.active,
        )
        .group_by(Student.class_id)
    )
    class_student_counts = dict(st_count_res.all())

    # Query submissions in date range
    sub_trend_res = await db.execute(
        select(
            AttendanceSubmission.date,
            AttendanceSubmission.class_id,
            AttendanceSubmission.absent_count,
        )
        .where(
            AttendanceSubmission.class_id.in_(scoped_class_ids),
            AttendanceSubmission.date >= start_trend_date,
            AttendanceSubmission.date <= today,
        )
        .order_by(AttendanceSubmission.date.asc())
    )
    daily_map: dict[date, dict[str, int]] = {}
    for sub_date, cid, absent_cnt in sub_trend_res.all():
        if sub_date not in daily_map:
            daily_map[sub_date] = {"absent": 0, "enrolled": 0}
        daily_map[sub_date]["absent"] += absent_cnt
        daily_map[sub_date]["enrolled"] += class_student_counts.get(cid, 0)

    # Query cases opened in date range for scoped entities
    case_trend_q = (
        select(func.date(Case.opened_at), func.count(Case.id))
        .where(
            func.date(Case.opened_at) >= start_trend_date,
            func.date(Case.opened_at) <= today,
        )
    )
    if current_user.role in {RoleEnum.head_teacher, RoleEnum.teacher}:
        case_trend_q = case_trend_q.where(Case.school_id == current_user.school_id)
    elif current_user.role == RoleEnum.sector_officer:
        case_trend_q = case_trend_q.join(Case.school).where(School.sector_id == current_user.sector_id)

    case_trend_res = await db.execute(case_trend_q.group_by(func.date(Case.opened_at)))
    daily_cases_map = dict(case_trend_res.all())

    attendance_trend: list[DailyAttendanceTrendItem] = []
    for d in sorted(daily_map.keys()):
        info = daily_map[d]
        abs_val = info["absent"]
        enr_val = max(info["enrolled"], abs_val)
        pres_val = max(0, enr_val - abs_val)
        cases_val = daily_cases_map.get(d, 0)

        attendance_trend.append(
            DailyAttendanceTrendItem(
                date=d.isoformat(),
                present=pres_val,
                absent=abs_val,
                enrolled=enr_val,
                cases=cases_val,
            )
        )

    return attendance_trend


@router.get("/overview", response_model=AnalyticsOverviewResponse, operation_id="get_analytics_overview")
async def get_analytics_overview(
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
    today = get_kigali_today()
    now_utc = utc_now()

    # Determine scope label
    if current_user.role == RoleEnum.admin:
        scope = ScopeInfo(level="national", name="Rwanda")
    elif current_user.role == RoleEnum.district_director:
        scope = ScopeInfo(level="district", name="District")
    elif current_user.role == RoleEnum.sector_officer:
        sec_res = await db.execute(select(Sector).where(Sector.id == current_user.sector_id))
        sec = sec_res.scalar_one_or_none()
        scope = ScopeInfo(level="sector", name=sec.name if sec else "Sector")
    elif current_user.role in {RoleEnum.head_teacher, RoleEnum.teacher}:
        sch_res = await db.execute(select(School).where(School.id == current_user.school_id))
        sch = sch_res.scalar_one_or_none()
        scope = ScopeInfo(level="school", name=sch.name if sch else "School")
    else:
        scope = ScopeInfo(level="user", name=current_user.full_name)

    # 1. Base query filter helper for students/schools
    st_q = select(func.count(Student.id)).where(Student.status == StudentStatusEnum.active)
    if current_user.role in {RoleEnum.head_teacher, RoleEnum.teacher}:
        st_q = st_q.where(Student.school_id == current_user.school_id)
    elif current_user.role == RoleEnum.sector_officer:
        st_q = st_q.join(Student.school).where(School.sector_id == current_user.sector_id)

    students_active_res = await db.execute(st_q)
    students_active = students_active_res.scalar() or 0

    # 2. Absent today
    abs_q = (
        select(func.count(Absence.id))
        .join(Student, Absence.student_id == Student.id)
        .where(Absence.date == today, Absence.status == AbsenceStatusEnum.active)
    )
    if current_user.role in {RoleEnum.head_teacher, RoleEnum.teacher}:
        abs_q = abs_q.where(Student.school_id == current_user.school_id)
    elif current_user.role == RoleEnum.sector_officer:
        abs_q = abs_q.join(School, Student.school_id == School.id).where(School.sector_id == current_user.sector_id)

    abs_today_res = await db.execute(abs_q)
    absent_today = abs_today_res.scalar() or 0

    # 3. Cases
    active_statuses = [
        CaseStatusEnum.open,
        CaseStatusEnum.mentor_assigned,
        CaseStatusEnum.visited,
        CaseStatusEnum.escalated_sector,
        CaseStatusEnum.escalated_district,
    ]
    cases_q = select(Case).options(selectinload(Case.student), selectinload(Case.school)).where(Case.status.in_(active_statuses))
    if current_user.role in {RoleEnum.head_teacher, RoleEnum.teacher}:
        cases_q = cases_q.where(Case.school_id == current_user.school_id)
    elif current_user.role == RoleEnum.sector_officer:
        cases_q = cases_q.join(Case.school).where(School.sector_id == current_user.sector_id)

    cases_res = await db.execute(cases_q)
    active_cases = cases_res.scalars().all()
    open_cases_count = len(active_cases)

    # Breakdown by level
    cases_by_level: dict[str, int] = {"2": 0, "3": 0, "4": 0}
    for c in active_cases:
        lvl_key = str(c.level)
        cases_by_level[lvl_key] = cases_by_level.get(lvl_key, 0) + 1

    # New cases last 7 days
    seven_days_ago = now_utc - timedelta(days=7)
    new_cases_7d = sum(1 for c in active_cases if c.opened_at >= seven_days_ago)

    # Returned cases last 30 days
    thirty_days_ago = now_utc - timedelta(days=30)
    ret_q = select(func.count(Case.id)).where(
        Case.status == CaseStatusEnum.resolved_returned,
        Case.resolved_at >= thirty_days_ago,
    )
    if current_user.role in {RoleEnum.head_teacher, RoleEnum.teacher}:
        ret_q = ret_q.where(Case.school_id == current_user.school_id)
    elif current_user.role == RoleEnum.sector_officer:
        ret_q = ret_q.join(Case.school).where(School.sector_id == current_user.sector_id)
    ret_res = await db.execute(ret_q)
    returned_30d = ret_res.scalar() or 0

    # Overdue cases (open > RULE_VISIT_SLA_SCHOOL_DAYS days)
    sla_cutoff = now_utc - timedelta(days=settings.RULE_VISIT_SLA_SCHOOL_DAYS)
    overdue_case_list: list[OverdueCaseItem] = []
    for c in active_cases:
        if c.opened_at <= sla_cutoff and c.status in (CaseStatusEnum.open, CaseStatusEnum.mentor_assigned):
            days_open = (now_utc - c.opened_at).days
            overdue_case_list.append(
                OverdueCaseItem(
                    id=c.id,
                    ref=c.ref,
                    student_name=c.student.full_name if c.student else "Unknown",
                    school_name=c.school.name if c.school else "Unknown",
                    level=c.level,
                    opened_at=c.opened_at,
                    days_open=days_open,
                )
            )

    visits_overdue = len(overdue_case_list)
    mentor_cases_active = sum(
        1
        for c in active_cases
        if c.mentor_id is not None or c.status == CaseStatusEnum.mentor_assigned
    )

    # Escalated cases (sector, district, or level >= 3)
    escalated_cases = [
        c
        for c in active_cases
        if c.status in (CaseStatusEnum.escalated_sector, CaseStatusEnum.escalated_district)
        or c.level >= 3
    ]
    escalated_cases.sort(key=lambda c: c.updated_at or c.opened_at, reverse=True)
    recent_escalations_count = len(escalated_cases)
    recent_escalations_list = [
        RecentEscalationItem(
            id=c.id,
            ref=c.ref,
            student_name=c.student.full_name if c.student else "Unknown",
            school_name=c.school.name if c.school else "Unknown",
            level=c.level,
            status=c.status.value,
            escalated_at=c.updated_at or c.opened_at,
        )
        for c in escalated_cases[:5]
    ]

    # Pending help requests
    hr_pending_statuses = [
        HelpRequestStatusEnum.new,
        HelpRequestStatusEnum.seen,
        HelpRequestStatusEnum.in_progress,
    ]
    hr_q = (
        select(HelpRequest)
        .options(selectinload(HelpRequest.student).selectinload(Student.school))
        .where(HelpRequest.status.in_(hr_pending_statuses))
    )
    if current_user.role in {RoleEnum.head_teacher, RoleEnum.teacher}:
        hr_q = hr_q.join(Student, HelpRequest.student_id == Student.id).where(
            Student.school_id == current_user.school_id
        )
    elif current_user.role == RoleEnum.sector_officer:
        hr_q = (
            hr_q.join(Student, HelpRequest.student_id == Student.id)
            .join(School, Student.school_id == School.id)
            .where(School.sector_id == current_user.sector_id)
        )
    hr_q = hr_q.order_by(desc(HelpRequest.created_at))
    hr_res = await db.execute(hr_q)
    all_pending_hr = hr_res.scalars().all()
    pending_help_requests_count = len(all_pending_hr)
    pending_help_requests_list = [
        PendingHelpRequestItem(
            id=hr.id,
            student_name=hr.student.full_name if hr.student else "Unknown",
            school_name=hr.student.school.name if (hr.student and hr.student.school) else "Unknown",
            barrier_code=hr.barrier_code.value
            if hasattr(hr.barrier_code, "value")
            else str(hr.barrier_code),
            status=hr.status.value,
            created_at=hr.created_at,
        )
        for hr in all_pending_hr[:5]
    ]

    # 4. Active Term
    term_res = await db.execute(
        select(Term).where(Term.start_date <= today, Term.end_date >= today).limit(1)
    )
    term_obj = term_res.scalar_one_or_none()
    active_term: ActiveTermInfo | None = None
    if term_obj:
        active_term = ActiveTermInfo(
            academic_year=term_obj.academic_year,
            term_no=term_obj.term_no,
            name=f"Term {term_obj.term_no} ({term_obj.academic_year})",
        )

    # 5. Attendance compliance & reporting gaps
    school_days_recent = await get_available_attendance_dates(db, max_backdate_days=5)
    class_q = select(Class).options(selectinload(Class.school))
    if current_user.role in {RoleEnum.head_teacher, RoleEnum.teacher}:
        class_q = class_q.where(Class.school_id == current_user.school_id)
    elif current_user.role == RoleEnum.sector_officer:
        class_q = class_q.join(Class.school).where(School.sector_id == current_user.sector_id)

    class_res = await db.execute(class_q)
    classes = class_res.scalars().all()

    total_expected = len(classes) * len(school_days_recent)
    total_submitted = 0
    reporting_gaps: list[ReportingGapItem] = []

    if school_days_recent and classes:
        cls_ids = [c.id for c in classes]
        sub_res = await db.execute(
            select(AttendanceSubmission.class_id, AttendanceSubmission.date).where(
                AttendanceSubmission.class_id.in_(cls_ids),
                AttendanceSubmission.date.in_(school_days_recent),
            )
        )
        submitted_set = set(sub_res.all())
        total_submitted = len(submitted_set)

        for c in classes:
            missing = [
                d.strftime("%d/%m")
                for d in school_days_recent
                if (c.id, d) not in submitted_set
            ]
            if missing:
                reporting_gaps.append(
                    ReportingGapItem(
                        class_name=c.name,
                        school_name=c.school.name if c.school else "Unknown",
                        missing_dates=missing,
                    )
                )

    compliance_pct = round(
        (total_submitted / total_expected * 100) if total_expected > 0 else 100.0, 1
    )

    # Classes missing today's submission
    today_is_school = await is_school_day(today, db)
    classes_missing_today_list: list[MissingClassItem] = []
    if today_is_school and classes:
        cls_today_sub_res = await db.execute(
            select(AttendanceSubmission.class_id).where(
                AttendanceSubmission.class_id.in_([c.id for c in classes]),
                AttendanceSubmission.date == today,
            )
        )
        cls_submitted_today = set(cls_today_sub_res.scalars().all())
        for c in classes:
            if c.id not in cls_submitted_today:
                classes_missing_today_list.append(
                    MissingClassItem(
                        class_id=c.id,
                        class_name=c.name,
                        school_name=c.school.name if c.school else "Unknown",
                    )
                )
    classes_missing_today_count = len(classes_missing_today_list)

    # 6. Daily Attendance Trends (90 days)
    attendance_trend = await compute_attendance_trend(
        db=db,
        current_user=current_user,
        scoped_class_ids=[c.id for c in classes],
        days=90,
    )

    return AnalyticsOverviewResponse(
        as_of=now_utc,
        timezone="Africa/Kigali (UTC+2)",
        kigali_today=today.isoformat(),
        scope=scope,
        kpis=OverviewKPIs(
            students_active=students_active,
            absent_today=absent_today,
            open_cases=open_cases_count,
            new_cases_7d=new_cases_7d,
            visits_overdue=visits_overdue,
            returned_30d=returned_30d,
            attendance_compliance_pct=compliance_pct,
            classes_missing_today=classes_missing_today_count,
            recent_escalations_count=recent_escalations_count,
            pending_help_requests_count=pending_help_requests_count,
            mentor_cases_active=mentor_cases_active,
        ),
        cases_by_level=cases_by_level,
        active_term=active_term,
        overdue_cases=overdue_case_list[:5],
        reporting_gaps=reporting_gaps[:5],
        classes_missing_today=classes_missing_today_list[:5],
        recent_escalations=recent_escalations_list,
        pending_help_requests=pending_help_requests_list,
        attendance_trend=attendance_trend,
    )


@router.get("/trends", response_model=list[DailyAttendanceTrendItem], operation_id="get_attendance_trends")
async def get_attendance_trends(
    days: int = 90,
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
    class_q = select(Class.id)
    if current_user.role in {RoleEnum.head_teacher, RoleEnum.teacher}:
        class_q = class_q.where(Class.school_id == current_user.school_id)
    elif current_user.role == RoleEnum.sector_officer:
        class_q = class_q.join(Class.school).where(School.sector_id == current_user.sector_id)

    class_res = await db.execute(class_q)
    scoped_class_ids = class_res.scalars().all()

    return await compute_attendance_trend(
        db=db,
        current_user=current_user,
        scoped_class_ids=scoped_class_ids,
        days=days,
    )


@router.get("/schools-compare", response_model=list[SchoolCompareItem], operation_id="compare_schools")
async def compare_schools(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            RoleEnum.admin,
            RoleEnum.district_director,
            RoleEnum.sector_officer,
        )
    ),
):
    today = get_kigali_today()
    now_utc = utc_now()
    thirty_days_ago = now_utc - timedelta(days=30)

    sch_q = select(School).options(selectinload(School.sector)).where(School.is_active.is_(True))
    if current_user.role == RoleEnum.sector_officer:
        sch_q = sch_q.where(School.sector_id == current_user.sector_id)

    sch_res = await db.execute(sch_q)
    schools = sch_res.scalars().all()

    items: list[SchoolCompareItem] = []

    for s in schools:
        # Active students count
        st_count_res = await db.execute(
            select(func.count(Student.id)).where(
                Student.school_id == s.id,
                Student.status == StudentStatusEnum.active,
            )
        )
        st_count = st_count_res.scalar() or 0

        # Absences today
        abs_count_res = await db.execute(
            select(func.count(Absence.id))
            .join(Student, Absence.student_id == Student.id)
            .where(
                Student.school_id == s.id,
                Absence.date == today,
                Absence.status == AbsenceStatusEnum.active,
            )
        )
        abs_count = abs_count_res.scalar() or 0
        abs_rate = round((abs_count / st_count * 100) if st_count > 0 else 0.0, 1)

        # Open cases
        open_cases_res = await db.execute(
            select(func.count(Case.id)).where(
                Case.school_id == s.id,
                Case.status.in_([
                    CaseStatusEnum.open,
                    CaseStatusEnum.mentor_assigned,
                    CaseStatusEnum.visited,
                    CaseStatusEnum.escalated_sector,
                    CaseStatusEnum.escalated_district,
                ]),
            )
        )
        open_cases = open_cases_res.scalar() or 0

        # Returned 30d
        ret_res = await db.execute(
            select(func.count(Case.id)).where(
                Case.school_id == s.id,
                Case.status == CaseStatusEnum.resolved_returned,
                Case.resolved_at >= thirty_days_ago,
            )
        )
        ret_count = ret_res.scalar() or 0

        # Classes compliance
        class_res = await db.execute(select(Class.id).where(Class.school_id == s.id))
        class_ids = class_res.scalars().all()
        school_days = await get_available_attendance_dates(db, max_backdate_days=5)
        expected = len(class_ids) * len(school_days)
        submitted = 0
        if expected > 0 and class_ids and school_days:
            sub_res = await db.execute(
                select(func.count(AttendanceSubmission.id)).where(
                    AttendanceSubmission.class_id.in_(class_ids),
                    AttendanceSubmission.date.in_(school_days),
                )
            )
            submitted = sub_res.scalar() or 0
        comp_rate = round((submitted / expected * 100) if expected > 0 else 100.0, 1)

        items.append(
            SchoolCompareItem(
                school_id=s.id,
                school_name=s.name,
                sector_name=s.sector.name if s.sector else "Unknown",
                students_active=st_count,
                absent_today=abs_count,
                absence_rate_pct=abs_rate,
                open_cases=open_cases,
                returned_30d=ret_count,
                attendance_compliance_pct=comp_rate,
            )
        )

    return items
