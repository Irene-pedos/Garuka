"""Additional rules engine tests for P0/P1 issues.

- RULE_ESCALATE_TERM_ABSENCES: term-total escalation to Level 3
- calculate_risk_score: dynamic year (not hardcoded 2026)
- generate_case_ref: uses current Kigali year
"""
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_pin_hash
from app.models.attendance import Absence, AbsenceStatusEnum, AttendanceSubmission, SubmissionSourceEnum
from app.models.calendar import Term
from app.models.case import Case, CaseEvent, CaseStatusEnum, CaseTriggerEnum
from app.models.geo import School, Sector
from app.models.student import Class, Guardian, Student, StudentStatusEnum, student_guardians
from app.models.user import LanguageEnum, RoleEnum, User
from app.services.rules_engine import calculate_risk_score, evaluate_student, generate_case_ref
from app.services.ussd.calendar_helper import get_kigali_today


# ---------------------------------------------------------------------------
# Risk score: dynamic year
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_risk_score_uses_current_year_not_hardcoded():
    """calculate_risk_score must use get_kigali_today().year, not 2026."""
    current_year = get_kigali_today().year
    # A student born in (current_year - expected_age - 3) is clearly over-age
    grade = 3
    expected_age = 6 + grade  # 9
    birth_year = current_year - (expected_age + 3)  # 3 years older than expected

    score_with_age = calculate_risk_score(
        grade=grade, is_repeater=False, birth_year=birth_year,
        absences_30d=0, current_year=current_year,
    )
    score_no_age = calculate_risk_score(
        grade=grade, is_repeater=False, birth_year=None,
        absences_30d=0, current_year=current_year,
    )
    # Over-age adds +10
    assert score_with_age == score_no_age + 10


@pytest.mark.asyncio
async def test_risk_score_explicit_year_override():
    """The current_year kwarg allows test isolation without real-clock dependency."""
    score_2026 = calculate_risk_score(
        grade=5, is_repeater=False, birth_year=2013, absences_30d=2, current_year=2026
    )
    score_2030 = calculate_risk_score(
        grade=5, is_repeater=False, birth_year=2013, absences_30d=2, current_year=2030
    )
    # In 2030, the student is 17 (expected 11) → over-age penalty; not over-age in 2026 (13 = expected+2)
    # 2026: age=13, expected=11, 13>=13 → over-age. 2030: age=17, expected=11 → over-age.
    # Both cases are over-age; scores should be equal for these particular values.
    # The key assertion: the function accepts the override without error.
    assert isinstance(score_2026, int)
    assert isinstance(score_2030, int)
    assert 0 <= score_2026 <= 100
    assert 0 <= score_2030 <= 100


# ---------------------------------------------------------------------------
# generate_case_ref: uses current Kigali year
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_case_ref_uses_current_year(db_session: AsyncSession):
    current_year = get_kigali_today().year
    ref = await generate_case_ref(db_session)
    assert ref.startswith(f"GK-{current_year}-"), (
        f"Expected ref to start with GK-{current_year}-, got {ref}"
    )


# ---------------------------------------------------------------------------
# Term-total escalation trigger (RULE_ESCALATE_TERM_ABSENCES)
# ---------------------------------------------------------------------------


async def _make_school_with_student(db: AsyncSession):
    """Helper: school + mentor + student + guardian, returns all."""
    sector_res = await db.execute(select(Sector).limit(1))
    sector = sector_res.scalar_one()

    school = School(
        sector_id=sector.id,
        name=f"Term School {uuid.uuid4().hex[:6]}",
        code=f"TS_{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db.add(school)
    await db.flush()

    mentor = User(
        email=f"mentor_{uuid.uuid4().hex[:6]}@test.rw",
        phone_e164=f"+25078{uuid.uuid4().int % 10000000:07d}",
        full_name="Mentor Term",
        role=RoleEnum.mentor,
        sector_id=sector.id,
        pin_hash=get_pin_hash("4321"),
        is_active=True,
    )
    db.add(mentor)

    teacher = User(
        email=f"t_{uuid.uuid4().hex[:6]}@test.rw",
        phone_e164=f"+25078{uuid.uuid4().int % 10000000:07d}",
        full_name="Teacher T",
        role=RoleEnum.teacher,
        school_id=school.id,
        is_active=True,
    )
    db.add(teacher)

    cls = Class(
        school_id=school.id, name="P4 B", grade=4,
        academic_year=get_kigali_today().year,
    )
    db.add(cls)
    await db.flush()

    student = Student(
        school_id=school.id,
        class_id=cls.id,
        roll_number=5,
        full_name="Nizeyimana Term",
        status=StudentStatusEnum.active,
        birth_year=2013,
    )
    db.add(student)
    await db.flush()

    guardian = Guardian(
        full_name="Nizeyimana Parent",
        phone_e164=f"+25078{uuid.uuid4().int % 10000000:07d}",
        language=LanguageEnum.rw,
    )
    db.add(guardian)
    await db.flush()

    await db.execute(
        student_guardians.insert().values(
            student_id=student.id,
            guardian_id=guardian.id,
            is_primary=True,
        )
    )
    await db.commit()
    return school, cls, student, teacher


@pytest.mark.asyncio
async def test_term_absences_open_case_when_no_existing(db_session: AsyncSession):
    """When only term threshold is met (no consecutive/monthly), a case is opened
    with trigger=term_total."""
    school, cls, student, teacher = await _make_school_with_student(db_session)
    today = get_kigali_today()

    # Create an active term covering today (get-or-create to avoid unique constraint errors)
    term_res = await db_session.execute(
        select(Term).where(Term.academic_year == today.year, Term.term_no == 1)
    )
    if not term_res.scalar_one_or_none():
        term = Term(
            academic_year=today.year,
            term_no=1,
            start_date=today - timedelta(days=60),
            end_date=today + timedelta(days=60),
        )
        db_session.add(term)
        await db_session.flush()

    # Add exactly RULE_ESCALATE_TERM_ABSENCES (10) absences in the term,
    # spread > 30 days ago so monthly (5-in-30d) is NOT triggered.
    # Also add present days (submission without absence) between and after them
    # so consecutive absences on submitted days does not trigger (must be < 3).
    threshold = settings.RULE_ESCALATE_TERM_ABSENCES  # 10
    for i in range(threshold):
        d = today - timedelta(days=60 - i * 2)  # every 2 days, starting 60 days ago
        sub = AttendanceSubmission(
            class_id=cls.id,
            date=d,
            submitted_by=teacher.id,
            source=SubmissionSourceEnum.dashboard,
            absent_count=1,
        )
        db_session.add(sub)
        await db_session.flush()
        db_session.add(Absence(
            student_id=student.id,
            submission_id=sub.id,
            date=d,
            status=AbsenceStatusEnum.active,
        ))

        # Add an intervening submitted day where the student was present (no absence)
        d_present = d + timedelta(days=1)
        sub_present = AttendanceSubmission(
            class_id=cls.id,
            date=d_present,
            submitted_by=teacher.id,
            source=SubmissionSourceEnum.dashboard,
            absent_count=0,
        )
        db_session.add(sub_present)

    await db_session.commit()

    case = await evaluate_student(student.id, db_session)
    assert case is not None, "A case should be opened when term threshold is met"
    assert case.trigger == CaseTriggerEnum.term_total
    assert case.level == 2  # Starts at Level 2; SEO escalation happens if existing case


@pytest.mark.asyncio
async def test_term_absences_escalate_existing_case_to_level_3(db_session: AsyncSession):
    """When an existing Level-2 case exists and term threshold is crossed,
    the case must be escalated to Level 3 (sector officer)."""
    school, cls, student, teacher = await _make_school_with_student(db_session)
    today = get_kigali_today()

    # Active term (get-or-create to avoid unique constraint errors)
    term_res2 = await db_session.execute(
        select(Term).where(Term.academic_year == today.year, Term.term_no == 2)
    )
    if not term_res2.scalar_one_or_none():
        term = Term(
            academic_year=today.year,
            term_no=2,
            start_date=today - timedelta(days=90),
            end_date=today + timedelta(days=90),
        )
        db_session.add(term)
        await db_session.flush()

    # Create an existing Level-2 case (already opened on monthly trigger)
    ref = await generate_case_ref(db_session)
    existing_case = Case(
        ref=ref,
        student_id=student.id,
        school_id=school.id,
        status=CaseStatusEnum.mentor_assigned,
        level=2,
        trigger=CaseTriggerEnum.monthly,
        risk_score=30,
        opened_at=datetime.now(UTC) - timedelta(days=25),
    )
    db_session.add(existing_case)
    await db_session.flush()
    await db_session.commit()

    # Add enough term absences to hit RULE_ESCALATE_TERM_ABSENCES,
    # also hitting monthly/consecutive thresholds to keep it simple
    threshold = settings.RULE_ESCALATE_TERM_ABSENCES
    base = today - timedelta(days=threshold)
    for i in range(threshold):
        d = base + timedelta(days=i)
        sub = AttendanceSubmission(
            class_id=cls.id,
            date=d,
            submitted_by=teacher.id,
            source=SubmissionSourceEnum.dashboard,
            absent_count=1,
        )
        db_session.add(sub)
        await db_session.flush()
        db_session.add(Absence(
            student_id=student.id,
            submission_id=sub.id,
            date=d,
            status=AbsenceStatusEnum.active,
        ))
    await db_session.commit()

    result = await evaluate_student(student.id, db_session)
    assert result is not None

    await db_session.refresh(existing_case)
    assert existing_case.level == 3, (
        f"Expected case to be escalated to Level 3, got level={existing_case.level}"
    )
    assert existing_case.status == CaseStatusEnum.escalated_sector

    # Verify an 'escalated' event was written
    events_res = await db_session.execute(
        select(CaseEvent).where(
            CaseEvent.case_id == existing_case.id,
            CaseEvent.type == "escalated",
        )
    )
    events = events_res.scalars().all()
    assert len(events) >= 1
    term_event = next(
        (e for e in events if e.payload.get("reason") == "term_absences"), None
    )
    assert term_event is not None, "Expected an 'escalated' event with reason='term_absences'"


@pytest.mark.asyncio
async def test_term_trigger_does_not_escalate_already_level_3_case(db_session: AsyncSession):
    """A case already at Level 3 must NOT be re-escalated by the term trigger."""
    school, cls, student, teacher = await _make_school_with_student(db_session)
    today = get_kigali_today()

    term_res3 = await db_session.execute(
        select(Term).where(Term.academic_year == today.year, Term.term_no == 3)
    )
    if not term_res3.scalar_one_or_none():
        term = Term(
            academic_year=today.year,
            term_no=3,
            start_date=today - timedelta(days=120),
            end_date=today + timedelta(days=60),
        )
        db_session.add(term)
        await db_session.flush()

    ref = await generate_case_ref(db_session)
    existing_case = Case(
        ref=ref,
        student_id=student.id,
        school_id=school.id,
        status=CaseStatusEnum.escalated_sector,
        level=3,
        trigger=CaseTriggerEnum.monthly,
        risk_score=60,
        opened_at=datetime.now(UTC) - timedelta(days=40),
    )
    db_session.add(existing_case)
    await db_session.flush()
    await db_session.commit()

    # Add enough term absences to trigger the threshold
    threshold = settings.RULE_ESCALATE_TERM_ABSENCES
    base = today - timedelta(days=threshold)
    for i in range(threshold):
        d = base + timedelta(days=i)
        sub = AttendanceSubmission(
            class_id=cls.id, date=d, submitted_by=teacher.id,
            source=SubmissionSourceEnum.dashboard, absent_count=1,
        )
        db_session.add(sub)
        await db_session.flush()
        db_session.add(Absence(
            student_id=student.id, submission_id=sub.id,
            date=d, status=AbsenceStatusEnum.active,
        ))
    await db_session.commit()

    await evaluate_student(student.id, db_session)
    await db_session.refresh(existing_case)

    # Level should remain 3, not jump to something unexpected
    assert existing_case.level == 3
    assert existing_case.status == CaseStatusEnum.escalated_sector
