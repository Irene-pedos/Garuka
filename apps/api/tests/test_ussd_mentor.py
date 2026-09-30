import uuid
from datetime import UTC, datetime, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_pin_hash
from app.models.case import (
    BarrierCodeEnum,
    Case,
    CaseStatusEnum,
    CaseTriggerEnum,
    MentorVisit,
    VisitOutcomeEnum,
)
from app.models.geo import School, Sector
from app.models.student import Class, Guardian, Student, StudentStatusEnum, student_guardians
from app.models.user import RoleEnum, User
from app.services.ussd.engine import handle_ussd_request


@pytest.mark.asyncio
async def test_ussd_mentor_full_flow(db_session: AsyncSession):
    sector_res = await db_session.execute(select(Sector).limit(1))
    sector = sector_res.scalar_one()

    school = School(
        sector_id=sector.id,
        name=f"Mentor School {uuid.uuid4().hex[:6]}",
        code=f"MS_{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(school)
    await db_session.flush()

    mentor_phone = f"+25078{uuid.uuid4().int % 10000000:07d}"
    mentor = User(
        email=f"mentor_flow_{uuid.uuid4().hex[:6]}@test.rw",
        phone_e164=mentor_phone,
        full_name="Jean Damascene Mentor",
        role=RoleEnum.mentor,
        sector_id=sector.id,
        pin_hash=get_pin_hash("4821"),
        is_active=True,
    )
    db_session.add(mentor)

    cls = Class(school_id=school.id, name="P6 A", grade=6, academic_year=2026)
    db_session.add(cls)
    await db_session.flush()

    student = Student(
        school_id=school.id,
        class_id=cls.id,
        roll_number=3,
        full_name="Hirwa Eric",
        status=StudentStatusEnum.active,
    )
    db_session.add(student)
    await db_session.flush()

    parent_phone = f"+25078{uuid.uuid4().int % 10000000:07d}"
    guardian = Guardian(
        full_name="Hirwa Parent",
        phone_e164=parent_phone,
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

    case = Case(
        ref=f"CAS-2026-{uuid.uuid4().hex[:4].upper()}",
        student_id=student.id,
        school_id=school.id,
        status=CaseStatusEnum.mentor_assigned,
        level=2,
        trigger=CaseTriggerEnum.consecutive,
        risk_score=50,
        mentor_id=mentor.id,
        opened_at=datetime.now(UTC) - timedelta(days=2),
    )
    db_session.add(case)
    await db_session.commit()

    session_id = f"sess_mentor_{uuid.uuid4()}"

    # Step 0: Initial prompt
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=mentor_phone,
        raw_text="",
        db=db_session,
    )
    assert kind == "CON"
    assert "PIN" in body or "umubare" in body

    # Step 1: Submit correct PIN -> Mentor Menu
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=mentor_phone,
        raw_text="4821",
        db=db_session,
    )
    assert kind == "CON"
    assert "Garuka" in body
    assert "1." in body or "Ibibazo" in body

    # Step 2: Choose 1 (Ibibazo nshinzwe / My cases) -> Case List
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=mentor_phone,
        raw_text="4821*1",
        db=db_session,
    )
    assert kind == "CON"
    assert "Hirwa" in body or "1." in body

    # Step 3: Choose Case 1 -> Case Detail Screen
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=mentor_phone,
        raw_text="4821*1*1",
        db=db_session,
    )
    assert kind == "CON"
    assert "Hirwa" in body
    assert "Gusura" in body or "Tangira" in body or "1." in body

    # Step 4: Choose 1 (Tangira gusura / Start Visit) -> Generates Code and prompts code/0
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=mentor_phone,
        raw_text="4821*1*1*1",
        db=db_session,
    )
    assert kind == "CON"
    assert "kode" in body.lower() or "0" in body

    # Step 5: Submit 0 (Unverified visit) -> Outcome Selection Screen
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=mentor_phone,
        raw_text="4821*1*1*1*0",
        db=db_session,
    )
    assert kind == "CON"
    assert "1." in body  # Outcome menu (1. Azagaruka, 2. Umugambi, 3. Akeneye ubufasha, 4. Yimukiye)

    # Step 6: Choose Outcome 3 (Akeneye ubufasha bw'umurenge / Needs sector help) -> Barrier Selection
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=mentor_phone,
        raw_text="4821*1*1*1*0*3",
        db=db_session,
    )
    assert kind == "CON"
    assert "1." in body  # Barrier menu (1. Amafaranga, 2. Inzara, etc.)

    # Step 7: Choose Barrier 1 (Amafaranga / COST) -> Atomic Commit -> END Success screen
    kind, body = await handle_ussd_request(
        session_id=session_id,
        service_code="*384*1234#",
        phone_number=mentor_phone,
        raw_text="4821*1*1*1*0*3*1",
        db=db_session,
    )
    assert kind == "END"
    assert "Murakoze" in body or "yanditswe" in body or "ubufasha" in body

    # Verify database state
    visit_res = await db_session.execute(
        select(MentorVisit).where(MentorVisit.case_id == case.id)
    )
    visit = visit_res.scalar_one_or_none()
    assert visit is not None
    assert visit.mentor_id == mentor.id
    assert visit.outcome == VisitOutcomeEnum.needs_sector_help
    assert visit.barrier_code == BarrierCodeEnum.COST
    assert visit.verified is False

    # Check case escalated to Level 3 / escalated_sector
    await db_session.refresh(case)
    assert case.level == 3
    assert case.status == CaseStatusEnum.escalated_sector
