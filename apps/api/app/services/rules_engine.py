import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.attendance import Absence, AbsenceStatusEnum, AttendanceSubmission
from app.models.base import utc_now
from app.models.calendar import Term
from app.models.case import Case, CaseEvent, CaseStatusEnum, CaseTriggerEnum
from app.models.geo import School
from app.models.student import Student, student_guardians
from app.models.user import RoleEnum, User
from app.services.sms.outbox_worker import enqueue_sms
from app.services.ussd.calendar_helper import get_kigali_today, is_school_day

logger = logging.getLogger("garuka.rules_engine")


async def calculate_student_metrics(
    student: Student,
    db: AsyncSession,
) -> tuple[int, int, int, int]:
    """
    Computes:
    - consecutive_absences: consecutive active absences on submitted school days (ending at latest submitted day)
    - absences_30d: active absences in last 30 calendar days
    - absences_term: active absences in current term
    - consecutive_present_days: consecutive days with submission and no active absence (streak of return)
    """
    today = get_kigali_today()
    class_id = student.class_id

    # 1. Fetch all submissions for student's class ordered by date desc
    sub_res = await db.execute(
        select(AttendanceSubmission.date)
        .where(AttendanceSubmission.class_id == class_id)
        .order_by(AttendanceSubmission.date.desc())
    )
    submitted_dates = sub_res.scalars().all()

    # Filter to only valid school days
    school_days: list[date] = []
    for d in submitted_dates:
        if await is_school_day(d, db):
            school_days.append(d)

    # 2. Fetch all active absences for student
    abs_res = await db.execute(
        select(Absence.date).where(
            Absence.student_id == student.id,
            Absence.status == AbsenceStatusEnum.active,
        )
    )
    absent_dates_set = set(abs_res.scalars().all())

    # 3. Consecutive absences (backward from latest submitted school day)
    consecutive_absences = 0
    for sd in school_days:
        if sd in absent_dates_set:
            consecutive_absences += 1
        else:
            break

    # 4. Consecutive present days (streak of attendance)
    consecutive_present = 0
    for sd in school_days:
        if sd not in absent_dates_set:
            consecutive_present += 1
        else:
            break

    # 5. Absences in last 30 calendar days
    thirty_days_ago = today - timedelta(days=30)
    absences_30d = sum(1 for d in absent_dates_set if d >= thirty_days_ago)

    # 6. Absences in current term
    term_res = await db.execute(
        select(Term).where(Term.start_date <= today, Term.end_date >= today).limit(1)
    )
    curr_term = term_res.scalar_one_or_none()
    if curr_term:
        absences_term = sum(
            1 for d in absent_dates_set if curr_term.start_date <= d <= curr_term.end_date
        )
    else:
        absences_term = absences_30d

    return consecutive_absences, absences_30d, absences_term, consecutive_present


def calculate_risk_score(
    grade: int,
    is_repeater: bool,
    birth_year: int | None,
    absences_30d: int,
    has_prior_case: bool = False,
) -> int:
    score = min(absences_30d, 10) * 5
    if grade in (5, 6):
        score += 15
    if is_repeater:
        score += 10
    if birth_year:
        age = 2026 - birth_year
        expected_age = 6 + grade
        if age >= expected_age + 2:
            score += 10
    if has_prior_case:
        score += 10
    return min(100, max(0, score))


async def assign_least_loaded_mentor(
    sector_id: uuid.UUID,
    db: AsyncSession,
) -> User | None:
    # Active mentors in this sector
    mentor_res = await db.execute(
        select(User).where(
            User.role == RoleEnum.mentor,
            User.sector_id == sector_id,
            User.is_active.is_(True),
        )
    )
    mentors = mentor_res.scalars().all()
    if not mentors:
        return None

    # Count active cases per mentor
    active_statuses = [
        CaseStatusEnum.open,
        CaseStatusEnum.mentor_assigned,
        CaseStatusEnum.visited,
        CaseStatusEnum.escalated_sector,
        CaseStatusEnum.escalated_district,
    ]
    eligible_mentors: list[tuple[User, int, int]] = []

    for m in mentors:
        active_cnt_res = await db.execute(
            select(func.count(Case.id)).where(
                Case.mentor_id == m.id,
                Case.status.in_(active_statuses),
            )
        )
        active_cnt = active_cnt_res.scalar() or 0
        if active_cnt < settings.MENTOR_MAX_ACTIVE_CASES:
            total_cnt_res = await db.execute(
                select(func.count(Case.id)).where(Case.mentor_id == m.id)
            )
            total_cnt = total_cnt_res.scalar() or 0
            eligible_mentors.append((m, active_cnt, total_cnt))

    if not eligible_mentors:
        return None

    # Pick least active, tie-breaker fewest total
    eligible_mentors.sort(key=lambda x: (x[1], x[2]))
    return eligible_mentors[0][0]


async def generate_case_ref(db: AsyncSession) -> str:
    count_res = await db.execute(select(func.count(Case.id)))
    cnt = (count_res.scalar() or 0) + 1
    return f"GK-2026-{cnt:06d}"


async def evaluate_student(
    student_id: uuid.UUID,
    db: AsyncSession,
) -> Case | None:
    """
    Evaluates student attendance against dropout rules.
    Called when an absence is submitted.
    """
    st_res = await db.execute(
        select(Student)
        .options(
            selectinload(Student.class_group),
            selectinload(Student.guardians),
            selectinload(Student.school).selectinload(School.sector),
        )
        .where(Student.id == student_id)
    )
    student = st_res.scalar_one_or_none()
    if not student or not student.class_group or not student.school:
        return None

    (
        consecutive_abs,
        absences_30d,
        absences_term,
        _consecutive_present,
    ) = await calculate_student_metrics(student, db)

    is_consecutive_trigger = consecutive_abs >= settings.RULE_CONSECUTIVE_DAYS
    is_monthly_trigger = absences_30d >= settings.RULE_MONTHLY_ABSENCES

    if not (is_consecutive_trigger or is_monthly_trigger):
        return None

    # Check for active case
    active_statuses = [
        CaseStatusEnum.open,
        CaseStatusEnum.mentor_assigned,
        CaseStatusEnum.visited,
        CaseStatusEnum.escalated_sector,
        CaseStatusEnum.escalated_district,
    ]
    existing_case_res = await db.execute(
        select(Case)
        .where(Case.student_id == student_id, Case.status.in_(active_statuses))
        .limit(1)
    )
    existing_case = existing_case_res.scalar_one_or_none()

    risk = calculate_risk_score(
        grade=student.class_group.grade,
        is_repeater=student.is_repeater,
        birth_year=student.birth_year,
        absences_30d=absences_30d,
    )

    if existing_case:
        # Update existing case risk score without creating a duplicate
        existing_case.risk_score = risk
        existing_case.last_evaluated_at = utc_now()
        event = CaseEvent(
            case_id=existing_case.id,
            type="evaluated",
            payload={
                "consecutive_absences": consecutive_abs,
                "absences_30d": absences_30d,
                "absences_term": absences_term,
                "risk_score": risk,
            },
        )
        db.add(event)
        await db.commit()
        return existing_case

    # Check for reopen within 30 days
    resolved_cutoff = utc_now() - timedelta(days=30)
    reopen_case_res = await db.execute(
        select(Case)
        .where(
            Case.student_id == student_id,
            Case.status == CaseStatusEnum.resolved_returned,
            Case.resolved_at >= resolved_cutoff,
        )
        .order_by(Case.resolved_at.desc())
        .limit(1)
    )
    reopen_case = reopen_case_res.scalar_one_or_none()

    trigger_type = (
        CaseTriggerEnum.consecutive if is_consecutive_trigger else CaseTriggerEnum.monthly
    )

    if reopen_case:
        reopen_case.reopened_count += 1
        reopen_case.status = CaseStatusEnum.open
        reopen_case.resolved_at = None
        reopen_case.level = 2
        reopen_case.risk_score = risk
        reopen_case.last_evaluated_at = utc_now()
        reopen_case.trigger = trigger_type

        # Re-assign mentor if possible
        mentor = await assign_least_loaded_mentor(student.school.sector_id, db)
        if mentor:
            reopen_case.mentor_id = mentor.id
            reopen_case.status = CaseStatusEnum.mentor_assigned

        db.add(
            CaseEvent(
                case_id=reopen_case.id,
                type="reopened",
                payload={"trigger": trigger_type.value, "risk_score": risk},
            )
        )
        target_case = reopen_case
    else:
        # Create new Case
        ref = await generate_case_ref(db)
        new_case = Case(
            ref=ref,
            student_id=student.id,
            school_id=student.school_id,
            status=CaseStatusEnum.open,
            level=2,
            trigger=trigger_type,
            risk_score=risk,
            opened_at=utc_now(),
            last_evaluated_at=utc_now(),
        )
        db.add(new_case)
        await db.flush()

        mentor = await assign_least_loaded_mentor(student.school.sector_id, db)
        if mentor:
            new_case.mentor_id = mentor.id
            new_case.status = CaseStatusEnum.mentor_assigned

        db.add(
            CaseEvent(
                case_id=new_case.id,
                type="opened",
                payload={"trigger": trigger_type.value, "risk_score": risk},
            )
        )
        target_case = new_case

    # Case assignment event & SMS to mentor
    if target_case.mentor_id:
        mentor_user = await db.get(User, target_case.mentor_id)
        db.add(
            CaseEvent(
                case_id=target_case.id,
                type="assigned",
                payload={"mentor_id": str(target_case.mentor_id)},
            )
        )
        if mentor_user and mentor_user.phone_e164:
            mentor_sms = (
                f"Garuka: new case {target_case.ref}. {student.full_name.split()[0]}, "
                f"{student.class_group.name}, {student.school.name}. "
                f"Dial {settings.USSD_SERVICE_CODE_DISPLAY} > My cases."
            )
            await enqueue_sms(
                db=db,
                to_e164=mentor_user.phone_e164,
                template_key="mentor_new_case",
                params={"ref": target_case.ref, "child": student.full_name},
                body=mentor_sms,
                dedupe_key=f"mentor_case:{target_case.id}:{mentor_user.id}",
                related_case_id=target_case.id,
                related_student_id=student.id,
            )

    # Parent notification SMS
    if student.guardians:
        primary_link = await db.execute(
            select(student_guardians.c.guardian_id).where(
                student_guardians.c.student_id == student.id,
                student_guardians.c.is_primary.is_(True),
            )
        )
        p_id = primary_link.scalar_one_or_none()
        guardian = next((g for g in student.guardians if g.id == p_id), student.guardians[0])
        if guardian and guardian.phone_e164 and not guardian.sms_opt_out:
            parent_sms = (
                f"Garuka: {student.full_name.split()[0]} has missed several school days. "
                f"A mentor may visit to help. Dial {settings.USSD_SERVICE_CODE_DISPLAY} for support."
            )
            await enqueue_sms(
                db=db,
                to_e164=guardian.phone_e164,
                template_key="parent_case_opened",
                params={"child": student.full_name},
                body=parent_sms,
                dedupe_key=f"case_opened:{target_case.id}",
                related_case_id=target_case.id,
                related_student_id=student.id,
            )

    await db.commit()
    return target_case


async def run_nightly_rules(db: AsyncSession) -> dict[str, int]:
    """
    Evaluates nightly (00:30 Africa/Kigali):
    1. SLA breach check: elapsed school days since mentor assignment > 5 -> Escalate to Level 3 (SEO)
    2. Level 4 District escalation check: Level 3 case open >= 14 days -> Escalate to Level 4
    3. Auto-resolve: student attended 10 consecutive submitted school days with 0 absence -> resolve
    """
    stats = {"sla_escalated": 0, "district_escalated": 0, "auto_resolved": 0}
    now = utc_now()

    # 1. SLA Breach Escalation (Level 2 mentor_assigned with > 5 elapsed school days)
    active_assigned_cases_res = await db.execute(
        select(Case)
        .options(selectinload(Case.school))
        .where(
            Case.status == CaseStatusEnum.mentor_assigned,
            Case.level == 2,
        )
    )
    for c in active_assigned_cases_res.scalars().all():
        days_open = (now.date() - c.opened_at.date()).days
        if days_open >= (settings.RULE_VISIT_SLA_SCHOOL_DAYS + 2):
            c.level = 3
            c.status = CaseStatusEnum.escalated_sector
            stats["sla_escalated"] += 1

            # Find SEO
            if c.school and c.school.sector_id:
                seo_res = await db.execute(
                    select(User).where(
                        User.role == RoleEnum.sector_officer,
                        User.sector_id == c.school.sector_id,
                        User.is_active.is_(True),
                    ).limit(1)
                )
                seo = seo_res.scalar_one_or_none()
                if seo:
                    c.sector_officer_id = seo.id
                    if seo.phone_e164:
                        await enqueue_sms(
                            db=db,
                            to_e164=seo.phone_e164,
                            template_key="seo_escalation",
                            params={"ref": c.ref, "school": c.school.name},
                            body=f"Garuka: case {c.ref} escalated at {c.school.name}. Open the dashboard to review.",
                            dedupe_key=f"seo_sla:{c.id}",
                            related_case_id=c.id,
                        )

            db.add(
                CaseEvent(
                    case_id=c.id,
                    type="escalated",
                    payload={"to_level": 3, "reason": "sla_breach"},
                )
            )

    # 2. District Escalation (Level 3 unresolved for >= 14 days)
    level3_res = await db.execute(
        select(Case).where(
            Case.status == CaseStatusEnum.escalated_sector,
            Case.level == 3,
        )
    )
    for c in level3_res.scalars().all():
        days_open = (now.date() - c.opened_at.date()).days
        if days_open >= settings.RULE_DISTRICT_ESCALATION_DAYS:
            c.level = 4
            c.status = CaseStatusEnum.escalated_district
            stats["district_escalated"] += 1
            db.add(
                CaseEvent(
                    case_id=c.id,
                    type="escalated",
                    payload={"to_level": 4, "reason": "district_escalation_sla"},
                )
            )

    # 3. Auto-resolve (10 consecutive school days present)
    active_cases_res = await db.execute(
        select(Case)
        .options(selectinload(Case.student))
        .where(
            Case.status.in_([
                CaseStatusEnum.open,
                CaseStatusEnum.mentor_assigned,
                CaseStatusEnum.visited,
                CaseStatusEnum.escalated_sector,
                CaseStatusEnum.escalated_district,
            ])
        )
    )
    for c in active_cases_res.scalars().all():
        if c.student:
            _, _, _, consecutive_present = await calculate_student_metrics(c.student, db)
            if consecutive_present >= settings.RULE_RETURN_STREAK_SCHOOL_DAYS:
                c.status = CaseStatusEnum.resolved_returned
                c.resolved_at = now
                stats["auto_resolved"] += 1
                db.add(
                    CaseEvent(
                        case_id=c.id,
                        type="resolved",
                        payload={"reason": "return_streak_10d", "streak": consecutive_present},
                    )
                )

    await db.commit()
    logger.info("Nightly rules engine completed: %s", stats)
    return stats
