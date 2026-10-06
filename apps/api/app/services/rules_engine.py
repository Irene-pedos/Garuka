import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.attendance import Absence, AbsenceStatusEnum, AttendanceSubmission
from app.models.base import utc_now
from app.models.calendar import Holiday, Term
from app.models.case import Case, CaseEvent, CaseStatusEnum, CaseTriggerEnum
from app.models.geo import School
from app.models.student import Student, student_guardians
from app.models.user import RoleEnum, User
from app.services.sms.outbox_worker import enqueue_sms
from app.services.ussd.calendar_helper import get_kigali_today, is_school_day

logger = logging.getLogger("garuka.rules_engine")


async def batch_check_school_days(
    dates: list[date],
    db: AsyncSession,
    cache: dict[date, bool] | None = None,
) -> dict[date, bool]:
    """Evaluates whether each date is a valid school day using at most 2 database queries for the batch."""
    if cache is None:
        cache = {}

    to_query = [d for d in set(dates) if d not in cache]
    if not to_query:
        return {d: cache[d] for d in dates}

    candidate_dates: list[date] = []
    for d in to_query:
        # Weekend check in memory (0=Monday, 4=Friday)
        if d.weekday() > 4:
            cache[d] = False
        else:
            candidate_dates.append(d)

    if not candidate_dates:
        return {d: cache[d] for d in dates}

    min_date = min(candidate_dates)
    max_date = max(candidate_dates)

    # 1. Fetch holidays in [min_date, max_date]
    hol_res = await db.execute(
        select(Holiday.date).where(Holiday.date.between(min_date, max_date))
    )
    holiday_set = set(hol_res.scalars().all())

    # 2. Fetch active terms overlapping [min_date, max_date]
    term_res = await db.execute(
        select(Term.start_date, Term.end_date).where(
            Term.start_date <= max_date,
            Term.end_date >= min_date,
        )
    )
    terms = term_res.all()

    for d in candidate_dates:
        if d in holiday_set:
            cache[d] = False
        else:
            cache[d] = any(t.start_date <= d <= t.end_date for t in terms)

    return {d: cache[d] for d in dates}


async def calculate_student_metrics(
    student: Student,
    db: AsyncSession,
    calendar_cache: dict[date, bool] | None = None,
) -> tuple[int, int, int, int]:
    """Computes:

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
    if not submitted_dates:
        return 0, 0, 0, 0

    # Filter to only valid school days using batch helper
    school_day_map = await batch_check_school_days(submitted_dates, db, calendar_cache)
    school_days = [d for d in submitted_dates if school_day_map.get(d, False)]

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
    current_year: int | None = None,
) -> int:
    """Compute a 0–100 risk score for prioritisation only (not a prediction).

    Args:
        grade: Student's grade number (1–6 for primary).
        is_repeater: True if the student is repeating the year.
        birth_year: Student's birth year; None means unknown (no over-age penalty).
        absences_30d: Active absences in the last 30 calendar days.
        has_prior_case: True if the student had a case in the last 12 months.
        current_year: Override the year used for age calculation (for testing).
                      Defaults to the current Africa/Kigali calendar year.
    """
    if current_year is None:
        current_year = get_kigali_today().year

    score = min(absences_30d, 10) * 5
    if grade in (5, 6):
        score += 15
    if is_repeater:
        score += 10
    if birth_year:
        age = current_year - birth_year
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

    # Count active cases per mentor using one grouped query
    active_statuses = [
        CaseStatusEnum.open,
        CaseStatusEnum.mentor_assigned,
        CaseStatusEnum.visited,
        CaseStatusEnum.escalated_sector,
        CaseStatusEnum.escalated_district,
    ]
    mentor_ids = [m.id for m in mentors]

    counts_q = (
        select(
            Case.mentor_id,
            func.count(Case.id).filter(Case.status.in_(active_statuses)).label("active_cnt"),
            func.count(Case.id).label("total_cnt"),
        )
        .where(Case.mentor_id.in_(mentor_ids))
        .group_by(Case.mentor_id)
    )
    counts_res = await db.execute(counts_q)
    counts_map = {row.mentor_id: (row.active_cnt, row.total_cnt) for row in counts_res}

    eligible_mentors: list[tuple[User, int, int]] = []
    for m in mentors:
        active_cnt, total_cnt = counts_map.get(m.id, (0, 0))
        if active_cnt < settings.MENTOR_MAX_ACTIVE_CASES:
            eligible_mentors.append((m, active_cnt, total_cnt))

    if not eligible_mentors:
        return None

    # Pick least active, tie-breaker fewest total
    eligible_mentors.sort(key=lambda x: (x[1], x[2]))
    return eligible_mentors[0][0]


async def generate_case_ref(db: AsyncSession) -> str:
    """Generate a unique case reference in the format GK-{YEAR}-{NNNNNN}.

    The year is derived from the current Africa/Kigali business date so the
    reference stays correct as calendar years advance.  A count-based sequence
    is used for readability, with a retry loop to handle the (rare) concurrent-
    insert collision.  For true high-concurrency safety, migrate to a
    PostgreSQL SEQUENCE in a future milestone.
    """
    current_year = get_kigali_today().year
    count_res = await db.execute(select(func.count(Case.id)))
    cnt = (count_res.scalar() or 0) + 1
    candidate = f"GK-{current_year}-{cnt:06d}"
    check = await db.execute(select(Case.id).where(Case.ref == candidate))
    while check.scalar_one_or_none() is not None:
        cnt += 1
        candidate = f"GK-{current_year}-{cnt:06d}"
        check = await db.execute(select(Case.id).where(Case.ref == candidate))
    return candidate


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
    is_term_trigger = absences_term >= settings.RULE_ESCALATE_TERM_ABSENCES

    if not (is_consecutive_trigger or is_monthly_trigger or is_term_trigger):
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
        # Update risk score
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

        # --- SPEC trigger 3: term-total escalation to Level 3 ---
        # Escalate only if not already at or above Level 3.
        if is_term_trigger and existing_case.level < 3:
            existing_case.level = 3
            existing_case.status = CaseStatusEnum.escalated_sector

            # Find SEO for the school's sector
            if student.school and student.school.sector_id:
                seo_res = await db.execute(
                    select(User).where(
                        User.role == RoleEnum.sector_officer,
                        User.sector_id == student.school.sector_id,
                        User.is_active.is_(True),
                    ).limit(1)
                )
                seo = seo_res.scalar_one_or_none()
                if seo:
                    existing_case.sector_officer_id = seo.id
                    if seo.phone_e164:
                        from app.services.sms.outbox_worker import enqueue_sms as _enqueue
                        await _enqueue(
                            db=db,
                            to_e164=seo.phone_e164,
                            template_key="seo_escalation",
                            params={"ref": existing_case.ref, "school": student.school.name},
                            body=(
                                f"Garuka: case {existing_case.ref} escalated at "
                                f"{student.school.name}. Open the dashboard to review."
                            ),
                            dedupe_key=f"seo_term:{existing_case.id}",
                            related_case_id=existing_case.id,
                            related_student_id=student.id,
                        )

            db.add(
                CaseEvent(
                    case_id=existing_case.id,
                    type="escalated",
                    payload={
                        "to_level": 3,
                        "reason": "term_absences",
                        "absences_term": absences_term,
                        "threshold": settings.RULE_ESCALATE_TERM_ABSENCES,
                    },
                )
            )

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

    # Determine trigger type for new-case creation (priority: consecutive > monthly > term_total)
    if is_consecutive_trigger:
        trigger_type = CaseTriggerEnum.consecutive
    elif is_monthly_trigger:
        trigger_type = CaseTriggerEnum.monthly
    else:
        trigger_type = CaseTriggerEnum.term_total

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
        if guardian and guardian.phone_e164 and not guardian.sms_opt_out and (guardian.consent_at is not None):
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
    calendar_cache: dict[date, bool] = {}
    for c in active_cases_res.scalars().all():
        if c.student:
            _, _, _, consecutive_present = await calculate_student_metrics(
                c.student, db, calendar_cache=calendar_cache
            )
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
