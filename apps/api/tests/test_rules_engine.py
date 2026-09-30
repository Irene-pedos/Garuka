import uuid
from datetime import UTC, date, datetime, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_pin_hash
from app.models.attendance import Absence, AbsenceStatusEnum, AttendanceSubmission, SubmissionSourceEnum
from app.models.case import Case, CaseStatusEnum, CaseTriggerEnum
from app.models.geo import School, Sector
from app.models.student import Class, Guardian, Student, StudentStatusEnum, student_guardians
from app.models.user import RoleEnum, User
from app.services.rules_engine import (
    calculate_risk_score,
    calculate_student_metrics,
    evaluate_student,
    run_nightly_rules,
)


@pytest.mark.asyncio
async def test_risk_score_calculation():
    # Base: grade 5 (weight 1.5 * 10 = 15)
    # Repeater (+15)
    # Over-age (+20) (e.g. birth_year 2011 for grade 5 in 2026 -> age 15, expected 10-11)
    # Absences: 6 in 30d (+25)
    # Prior case (+15)
    score = calculate_risk_score(
        grade=5,
        is_repeater=True,
        birth_year=2011,
        absences_30d=6,
        has_prior_case=True,
    )
    assert score >= 70
    assert score <= 100


@pytest.mark.asyncio
async def test_rules_engine_consecutive_absences_opens_case(db_session: AsyncSession):
    sector_res = await db_session.execute(select(Sector).limit(1))
    sector = sector_res.scalar_one()

    school = School(
        sector_id=sector.id,
        name=f"Rules School {uuid.uuid4().hex[:6]}",
        code=f"RS_{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(school)
    await db_session.flush()

    mentor = User(
        email=f"mentor_{uuid.uuid4().hex[:6]}@test.rw",
        phone_e164=f"+25078{uuid.uuid4().int % 10000000:07d}",
        full_name="Community Mentor One",
        role=RoleEnum.mentor,
        sector_id=sector.id,
        pin_hash=get_pin_hash("4821"),
        is_active=True,
    )
    db_session.add(mentor)

    cls = Class(school_id=school.id, name="P4 A", grade=4, academic_year=2026)
    db_session.add(cls)
    await db_session.flush()

    student = Student(
        school_id=school.id,
        class_id=cls.id,
        roll_number=10,
        full_name="Murenzi Patrick",
        status=StudentStatusEnum.active,
        birth_year=2014,
    )
    db_session.add(student)
    await db_session.flush()

    guardian = Guardian(
        full_name="Murenzi Father",
        phone_e164=f"+25078{uuid.uuid4().int % 10000000:07d}",
    )
    db_session.add(guardian)
    await db_session.flush()

    await db_session.execute(
        student_guardians.insert().values(
            student_id=student.id,
            guardian_id=guardian.id,
            is_primary=True,
        )
    )

    # Submit 3 consecutive absences on consecutive weekdays (Monday, Tuesday, Wednesday)
    base_date = date(2026, 3, 2)  # Monday
    teacher = User(
        email=f"t_{uuid.uuid4().hex[:6]}@test.rw",
        phone_e164=f"+25078{uuid.uuid4().int % 10000000:07d}",
        full_name="Teacher T",
        role=RoleEnum.teacher,
        school_id=school.id,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.flush()

    for day_offset in range(3):
        cur_date = base_date + timedelta(days=day_offset)
        sub = AttendanceSubmission(
            class_id=cls.id,
            date=cur_date,
            submitted_by=teacher.id,
            source=SubmissionSourceEnum.dashboard,
            absent_count=1,
        )
        db_session.add(sub)
        await db_session.flush()

        abs_rec = Absence(
            student_id=student.id,
            submission_id=sub.id,
            date=cur_date,
            status=AbsenceStatusEnum.active,
        )
        db_session.add(abs_rec)

    await db_session.commit()

    # Trigger evaluation
    case = await evaluate_student(student.id, db_session)
    assert case is not None
    assert case.student_id == student.id
    assert case.status == CaseStatusEnum.mentor_assigned
    assert case.mentor_id is not None
    assert case.trigger == CaseTriggerEnum.consecutive
    assert case.level == 2
    assert case.risk_score > 0


@pytest.mark.asyncio
async def test_nightly_rules_auto_resolve(db_session: AsyncSession):
    sector_res = await db_session.execute(select(Sector).limit(1))
    sector = sector_res.scalar_one()

    school = School(
        sector_id=sector.id,
        name=f"Nightly School {uuid.uuid4().hex[:6]}",
        code=f"NS_{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(school)
    await db_session.flush()

    cls = Class(school_id=school.id, name="P3 A", grade=3, academic_year=2026)
    db_session.add(cls)
    await db_session.flush()

    student = Student(
        school_id=school.id,
        class_id=cls.id,
        roll_number=7,
        full_name="Uwase Nadia",
        status=StudentStatusEnum.active,
    )
    db_session.add(student)
    await db_session.flush()

    # Create an open case for student
    from app.services.rules_engine import generate_case_ref
    ref = await generate_case_ref(db_session)
    case = Case(
        ref=ref,
        student_id=student.id,
        school_id=school.id,
        status=CaseStatusEnum.mentor_assigned,
        level=2,
        trigger=CaseTriggerEnum.consecutive,
        risk_score=40,
        opened_at=datetime.now(UTC) - timedelta(days=20),
    )
    db_session.add(case)

    # Add 10 consecutive submitted school days with 0 absences for Nadia
    teacher = User(
        email=f"t_{uuid.uuid4().hex[:6]}@test.rw",
        phone_e164=f"+25078{uuid.uuid4().int % 10000000:07d}",
        full_name="Teacher Nadia",
        role=RoleEnum.teacher,
        school_id=school.id,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.flush()

    # 10 weekdays
    dates = [
        date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4), date(2026, 3, 5), date(2026, 3, 6),
        date(2026, 3, 9), date(2026, 3, 10), date(2026, 3, 11), date(2026, 3, 12), date(2026, 3, 13)
    ]
    for d in dates:
        sub = AttendanceSubmission(
            class_id=cls.id,
            date=d,
            submitted_by=teacher.id,
            source=SubmissionSourceEnum.dashboard,
            absent_count=0,
        )
        db_session.add(sub)

    await db_session.commit()

    stats = await run_nightly_rules(db_session)
    assert stats["auto_resolved"] >= 1

    await db_session.refresh(case)
    assert case.status == CaseStatusEnum.resolved_returned
    assert case.resolved_at is not None


@pytest.mark.asyncio
async def test_generate_case_ref_collision_free(db_session: AsyncSession):
    from app.services.rules_engine import generate_case_ref

    ref1 = await generate_case_ref(db_session)
    # Manually create a case with this ref to simulate collision
    sector_res = await db_session.execute(select(Sector).limit(1))
    sector = sector_res.scalar_one()

    school = School(
        sector_id=sector.id,
        name=f"Coll School {uuid.uuid4().hex[:6]}",
        code=f"CS_{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(school)
    await db_session.flush()

    cls = Class(school_id=school.id, name="P1 Test", grade=1, academic_year=2026)
    db_session.add(cls)
    await db_session.flush()

    st = Student(
        school_id=school.id,
        class_id=cls.id,
        roll_number=1,
        full_name="Collision Student",
        status=StudentStatusEnum.active,
    )
    db_session.add(st)
    await db_session.flush()

    dummy_case = Case(
        ref=ref1,
        student_id=st.id,
        school_id=school.id,
        status=CaseStatusEnum.open,
        level=2,
        trigger=CaseTriggerEnum.consecutive,
        risk_score=50,
    )
    db_session.add(dummy_case)
    await db_session.commit()

    # Next generated ref must NOT collide with ref1
    ref2 = await generate_case_ref(db_session)
    assert ref2 != ref1
    assert ref2.startswith("GK-2026-")
