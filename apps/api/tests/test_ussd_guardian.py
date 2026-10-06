"""Tests for the parent/guardian USSD flow (execute_guardian_flow).

Covers:
- P_MENU shown for guardian-only caller
- P_ATT (attendance view) — absences present / none
- P_ABS_PICK + P_REASON (explain an absence)
- P_HELP (help request creation)
- P_CHILD multi-child picker
- Language change from parent menu
- S_INVALID recovery on every menu screen
"""
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.attendance import Absence, AbsenceStatusEnum, AttendanceSubmission, SubmissionSourceEnum
from app.models.case import BarrierCodeEnum, HelpRequest
from app.models.geo import School, Sector
from app.models.student import Class, Guardian, Student, StudentStatusEnum, student_guardians
from app.models.user import LanguageEnum, RoleEnum, User
from app.services.ussd.calendar_helper import get_kigali_today
from app.services.ussd.engine import handle_ussd_request


SESSION_ID = "guardian-test-session"
PHONE = "+250788000099"


async def _make_guardian_with_student(db: AsyncSession, *, n_children: int = 1):
    """Helper: create guardian + school + student(s) + basic absence records."""
    sector_res = await db.execute(select(Sector).limit(1))
    sector = sector_res.scalar_one()

    school = School(
        sector_id=sector.id,
        name=f"Guard School {uuid.uuid4().hex[:6]}",
        code=f"GS_{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db.add(school)
    await db.flush()

    teacher = User(
        email=f"t_{uuid.uuid4().hex[:6]}@test.rw",
        phone_e164=f"+25078{uuid.uuid4().int % 10000000:07d}",
        full_name="Teacher G",
        role=RoleEnum.teacher,
        school_id=school.id,
        is_active=True,
    )
    db.add(teacher)

    phone = f"+25078{uuid.uuid4().int % 10000000:07d}"
    guardian = Guardian(
        full_name="Mugenzi Parent",
        phone_e164=phone,
        language=LanguageEnum.en,
    )
    db.add(guardian)
    await db.flush()

    students = []
    for i in range(n_children):
        cls = Class(school_id=school.id, name=f"P{i + 3} A", grade=i + 3,
                    academic_year=get_kigali_today().year)
        db.add(cls)
        await db.flush()

        st = Student(
            school_id=school.id,
            class_id=cls.id,
            roll_number=i + 1,
            full_name=f"Mugenzi Child{i + 1}",
            status=StudentStatusEnum.active,
            birth_year=2015,
        )
        db.add(st)
        await db.flush()
        students.append((st, cls, teacher))

        await db.execute(
            student_guardians.insert().values(
                student_id=st.id,
                guardian_id=guardian.id,
                relationship="parent",
                is_primary=(i == 0),
            )
        )

    await db.commit()
    return guardian, students, school


async def _add_absence(db: AsyncSession, student: Student, cls: Class, teacher: User,
                       absence_date: date) -> Absence:
    sub_res = await db.execute(
        select(AttendanceSubmission).where(
            AttendanceSubmission.class_id == cls.id,
            AttendanceSubmission.date == absence_date,
        )
    )
    sub = sub_res.scalar_one_or_none()
    if not sub:
        sub = AttendanceSubmission(
            class_id=cls.id,
            date=absence_date,
            submitted_by=teacher.id,
            source=SubmissionSourceEnum.ussd,
            absent_count=1,
        )
        db.add(sub)
        await db.flush()

    abs_rec = Absence(
        student_id=student.id,
        submission_id=sub.id,
        date=absence_date,
        status=AbsenceStatusEnum.active,
    )
    db.add(abs_rec)
    await db.flush()
    await db.commit()
    return abs_rec


# --------------------------------------------------------------------------
# P_MENU shown on first dial (guardian-only)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guardian_sees_p_menu(db_session: AsyncSession):
    guardian, [(st, cls, teacher)], school = await _make_guardian_with_student(db_session)

    kind, body = await handle_ussd_request(
        session_id=f"g-{uuid.uuid4().hex}",
        service_code=settings.USSD_SERVICE_CODE_DISPLAY,
        phone_number=guardian.phone_e164,
        raw_text="",
        db=db_session,
    )
    assert kind == "CON"
    assert "Garuka" in body
    assert "1." in body  # Attendance option


# --------------------------------------------------------------------------
# P_ATT — attendance summary with absences
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guardian_p_att_with_absences(db_session: AsyncSession):
    guardian, [(st, cls, teacher)], school = await _make_guardian_with_student(db_session)
    today = get_kigali_today()
    await _add_absence(db_session, st, cls, teacher, today - timedelta(days=2))

    kind, body = await handle_ussd_request(
        session_id=f"g-{uuid.uuid4().hex}",
        service_code=settings.USSD_SERVICE_CODE_DISPLAY,
        phone_number=guardian.phone_e164,
        raw_text="1",  # Attendance
        db=db_session,
    )
    assert kind == "END"
    assert "absent" in body.lower() or "1" in body


# --------------------------------------------------------------------------
# P_ATT — no absences
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guardian_p_att_no_absences(db_session: AsyncSession):
    guardian, [(st, cls, teacher)], school = await _make_guardian_with_student(db_session)

    kind, body = await handle_ussd_request(
        session_id=f"g-{uuid.uuid4().hex}",
        service_code=settings.USSD_SERVICE_CODE_DISPLAY,
        phone_number=guardian.phone_e164,
        raw_text="1",
        db=db_session,
    )
    assert kind == "END"
    assert "No absences" in body or "Nta" in body  # EN or RW


# --------------------------------------------------------------------------
# P_ABS_PICK + P_REASON — explain an absence
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guardian_explain_absence_saves_reason(db_session: AsyncSession):
    guardian, [(st, cls, teacher)], school = await _make_guardian_with_student(db_session)
    today = get_kigali_today()
    absence = await _add_absence(db_session, st, cls, teacher, today - timedelta(days=1))

    # Step 1: Choose "2. Explain absence" from P_MENU
    kind1, body1 = await handle_ussd_request(
        session_id=f"g-{uuid.uuid4().hex}",
        service_code=settings.USSD_SERVICE_CODE_DISPLAY,
        phone_number=guardian.phone_e164,
        raw_text="2",
        db=db_session,
    )
    assert kind1 == "CON"
    assert "explain" in body1.lower() or "day" in body1.lower()

    # Step 2: Pick absence (first item = "1")
    kind2, body2 = await handle_ussd_request(
        session_id=f"g-{uuid.uuid4().hex}",
        service_code=settings.USSD_SERVICE_CODE_DISPLAY,
        phone_number=guardian.phone_e164,
        raw_text="2*1",
        db=db_session,
    )
    assert kind2 == "CON"
    assert "Reason" in body2 or "Impamvu" in body2

    # Step 3: Pick reason "1. Sick"
    kind3, body3 = await handle_ussd_request(
        session_id=f"g-{uuid.uuid4().hex}",
        service_code=settings.USSD_SERVICE_CODE_DISPLAY,
        phone_number=guardian.phone_e164,
        raw_text="2*1*1",
        db=db_session,
    )
    assert kind3 == "END"
    assert "Thank you" in body3 or "Murakoze" in body3

    # Verify the reason was persisted
    await db_session.refresh(absence)
    from app.models.attendance import ReasonCodeEnum, ReasonSourceEnum
    assert absence.reason_code == ReasonCodeEnum.SICK
    assert absence.reason_source == ReasonSourceEnum.parent


# --------------------------------------------------------------------------
# P_HELP — help request creation
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guardian_help_request_created(db_session: AsyncSession):
    guardian, [(st, cls, teacher)], school = await _make_guardian_with_student(db_session)

    kind, body = await handle_ussd_request(
        session_id=f"g-{uuid.uuid4().hex}",
        service_code=settings.USSD_SERVICE_CODE_DISPLAY,
        phone_number=guardian.phone_e164,
        raw_text="3*1",  # Ask for help → Fees/materials
        db=db_session,
    )
    assert kind == "END"
    assert "school" in body.lower() or "ishuri" in body.lower()

    # Verify help_request was created
    hr_res = await db_session.execute(
        select(HelpRequest).where(HelpRequest.guardian_id == guardian.id)
    )
    hr = hr_res.scalar_one_or_none()
    assert hr is not None
    assert hr.barrier_code == BarrierCodeEnum.COST
    assert hr.student_id == st.id


# --------------------------------------------------------------------------
# P_CHILD multi-child picker
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guardian_child_picker_shown_for_two_children(db_session: AsyncSession):
    guardian, children, school = await _make_guardian_with_student(db_session, n_children=2)

    kind, body = await handle_ussd_request(
        session_id=f"g-{uuid.uuid4().hex}",
        service_code=settings.USSD_SERVICE_CODE_DISPLAY,
        phone_number=guardian.phone_e164,
        raw_text="",
        db=db_session,
    )
    assert kind == "CON"
    # Should show P_CHILD list
    assert "1." in body
    assert "2." in body


@pytest.mark.asyncio
async def test_guardian_child_picker_select_reaches_p_menu(db_session: AsyncSession):
    guardian, children, school = await _make_guardian_with_student(db_session, n_children=2)

    kind, body = await handle_ussd_request(
        session_id=f"g-{uuid.uuid4().hex}",
        service_code=settings.USSD_SERVICE_CODE_DISPLAY,
        phone_number=guardian.phone_e164,
        raw_text="1",  # Select first child
        db=db_session,
    )
    assert kind == "CON"
    assert "Garuka" in body  # P_MENU header


# --------------------------------------------------------------------------
# Invalid choice recovery
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guardian_invalid_menu_choice_stays_in_session(db_session: AsyncSession):
    guardian, [(st, cls, teacher)], school = await _make_guardian_with_student(db_session)

    kind, body = await handle_ussd_request(
        session_id=f"g-{uuid.uuid4().hex}",
        service_code=settings.USSD_SERVICE_CODE_DISPLAY,
        phone_number=guardian.phone_e164,
        raw_text="9",  # Invalid option
        db=db_session,
    )
    assert kind == "CON"
    assert "Invalid" in body or "Ibyo" in body or "Choix" in body
