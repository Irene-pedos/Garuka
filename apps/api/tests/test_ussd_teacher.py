import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_pin_hash
from app.models.attendance import AttendanceSubmission
from app.models.geo import School
from app.models.student import Class, Student, StudentStatusEnum
from app.models.user import RoleEnum, User
from app.services.ussd.engine import handle_ussd_request



@pytest.mark.asyncio
async def test_ussd_unregistered_phone(db_session: AsyncSession):
    phone = "+250789999999"
    kind, body = await handle_ussd_request(
        session_id=f"sess_{uuid.uuid4()}",
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="",
        db=db_session,
    )
    assert kind == "END"
    assert "Uyu mubare ntabwo wanditswe" in body or "Garuka" in body


@pytest.mark.asyncio
async def test_ussd_teacher_pin_setup_and_auth(db_session: AsyncSession):
    # Create new teacher without PIN
    schools_res = await db_session.execute(select(School).limit(1))
    school = schools_res.scalar_one()

    phone = f"+25078{uuid.uuid4().int % 10000000:07d}"
    teacher = User(
        email=f"teacher_{uuid.uuid4().hex[:6]}@example.com",
        phone_e164=phone,
        full_name="New Test Teacher",
        role=RoleEnum.teacher,
        school_id=school.id,
        pin_hash=None,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()

    session_id = f"sess_{uuid.uuid4()}"

    # Step 0: Initial dial -> Prompt to choose PIN
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="",
        db=db_session,
    )
    assert kind == "CON"
    assert "Shyiraho umubare w'ibanga" in body or "imibare 4" in body

    # Step 1: Input invalid PIN (e.g. 1234)
    sess_bad = f"sess_bad_{uuid.uuid4()}"
    kind, body = await handle_ussd_request(
        session_id=sess_bad,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="1234",
        db=db_session,
    )
    assert kind == "END"
    assert "1234" in body or "idasanzwe" in body

    # Step 2: Fresh session: Input valid PIN 5829 -> Prompt to confirm
    sess_valid = f"sess_valid_{uuid.uuid4()}"
    kind, body = await handle_ussd_request(
        session_id=sess_valid,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="5829",
        db=db_session,
    )
    assert kind == "CON"
    assert "Subiramo umubare" in body or "Repeat" in body

    # Step 3: Confirmation mismatch
    kind, body = await handle_ussd_request(
        session_id=sess_valid,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="5829*9999",
        db=db_session,
    )
    assert kind == "END"
    assert "ntiyahuye" in body or "match" in body


    # Step 4: Correct confirmation (in another fresh session)
    sess_confirm = f"sess_confirm_{uuid.uuid4()}"
    kind, body = await handle_ussd_request(
        session_id=sess_confirm,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="5829*5829",
        db=db_session,
    )

    assert kind == "END"
    assert "wabitswe" in body or "saved" in body


    # Verify PIN hash set in DB
    await db_session.refresh(teacher)
    assert teacher.pin_hash is not None


@pytest.mark.asyncio
async def test_ussd_teacher_pin_lockout_after_3_attempts(db_session: AsyncSession):
    schools_res = await db_session.execute(select(School).limit(1))
    school = schools_res.scalar_one()

    phone = f"+25078{uuid.uuid4().int % 10000000:07d}"
    teacher = User(
        email=f"lockout_{uuid.uuid4().hex[:6]}@example.com",
        phone_e164=phone,
        full_name="Lockout Teacher",
        role=RoleEnum.teacher,
        school_id=school.id,
        pin_hash=get_pin_hash("4821"),
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()

    # Attempt 1: wrong PIN
    sess1 = f"sess_wrong_1_{uuid.uuid4()}"
    kind, body = await handle_ussd_request(
        session_id=sess1,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="1111",
        db=db_session,
    )
    assert kind == "END"
    assert "si wo" in body or "Ongera uhamagare" in body

    # Attempt 2: wrong PIN
    sess2 = f"sess_wrong_2_{uuid.uuid4()}"
    await handle_ussd_request(
        session_id=sess2,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="2222",
        db=db_session,
    )

    # Attempt 3: wrong PIN -> locked
    sess3 = f"sess_wrong_3_{uuid.uuid4()}"
    kind, body = await handle_ussd_request(
        session_id=sess3,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="3333",
        db=db_session,
    )
    assert kind == "END"
    assert "Konti yawe yafunzwe" in body or "bloqué" in body or "locked" in body or "iminota 30" in body

    await db_session.refresh(teacher)
    assert teacher.pin_failed_count == 3
    assert teacher.pin_locked_until is not None


@pytest.mark.asyncio
async def test_ussd_teacher_full_attendance_flow(db_session: AsyncSession):
    from app.models.geo import Sector
    from app.models.student import StudentStatusEnum

    sector_res = await db_session.execute(select(Sector).limit(1))
    sector = sector_res.scalar_one()

    test_school = School(
        sector_id=sector.id,
        name=f"Test School {uuid.uuid4().hex[:6]}",
        code=f"TS_{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(test_school)
    await db_session.flush()

    phone = f"+25078{uuid.uuid4().int % 10000000:07d}"
    teacher = User(
        email=f"teacher_{uuid.uuid4().hex[:6]}@test.rw",
        phone_e164=phone,
        full_name="Isolated Teacher",
        role=RoleEnum.teacher,
        school_id=test_school.id,
        pin_hash=get_pin_hash("4821"),
        is_active=True,
    )
    db_session.add(teacher)

    cls = Class(
        school_id=test_school.id,
        name="P5 Test",
        grade=5,
        academic_year=2026,
    )
    db_session.add(cls)
    await db_session.flush()

    st1 = Student(
        school_id=test_school.id,
        class_id=cls.id,
        roll_number=1,
        full_name="Keza Alice",
        status=StudentStatusEnum.active,
    )
    st2 = Student(
        school_id=test_school.id,
        class_id=cls.id,
        roll_number=2,
        full_name="Mugisha Bob",
        status=StudentStatusEnum.active,
    )
    db_session.add_all([st1, st2])
    await db_session.commit()

    session_id = f"sess_full_att_{uuid.uuid4()}"

    # Step 0: Prompt PIN
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="",
        db=db_session,
    )
    assert kind == "CON"
    assert "Injiza umubare" in body or "PIN" in body

    # Step 1: Submit correct PIN -> Teacher Menu
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="4821",
        db=db_session,
    )
    assert kind == "CON"
    assert "Garuka" in body
    assert "1." in body

    # Step 2: Choose 1 (Kwandika abitabiriye) -> Auto-selects single class and shows Date Selection
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="4821*1",
        db=db_session,
    )
    assert kind == "CON"
    assert "itariki" in body.lower() or "date" in body.lower() or "uyu munsi" in body.lower()

    # Step 3: Select Date 1 (Today) -> Roll Number Entry
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="4821*1*1",
        db=db_session,
    )
    assert kind == "CON"
    assert "numero y'umunyeshuri" in body.lower() or "roll" in body.lower()




    # Step 4: Mark roll 1 absent
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="4821*1*1*1",
        db=db_session,
    )
    assert kind == "CON"
    assert "1" in body

    # Step 5: Mark roll 2 absent
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="4821*1*1*1*2",
        db=db_session,
    )
    assert kind == "CON"

    # Step 6: Finish roll entry with 0 -> Confirmation screen
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="4821*1*1*1*2*0",
        db=db_session,
    )
    assert kind == "CON"
    assert "Bika" in body or "basibye" in body or "Confirm" in body
    assert "1, 2" in body or "2" in body

    # Step 7: Confirm submission (1. Yego / Confirm) -> Success screen (END)
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="4821*1*1*1*2*0*1",
        db=db_session,
    )
    assert kind == "END"
    assert "Byabitswe" in body or "Success" in body or "recorded" in body

    # Verify DB records
    sub_res = await db_session.execute(
        select(AttendanceSubmission).where(AttendanceSubmission.class_id == cls.id)
    )
    sub = sub_res.scalar_one_or_none()
    assert sub is not None
    assert sub.absent_count == 2

    # Step 8: Verify Idempotency - repeating identical request returns cached result
    kind2, body2 = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=phone,
        raw_text="4821*1*1*1*2*0*1",
        db=db_session,
    )
    assert kind2 == kind
    assert body2 == body

