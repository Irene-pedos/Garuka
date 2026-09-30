import uuid
from datetime import UTC, datetime, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_pin_hash
from app.models.case import Case, CaseStatusEnum, CaseTriggerEnum
from app.models.geo import School, Sector
from app.models.student import Class, Student, StudentStatusEnum
from app.models.user import RoleEnum, User


@pytest.fixture
async def setup_cases_data(db_session: AsyncSession):
    sector_res = await db_session.execute(select(Sector).limit(1))
    sector = sector_res.scalar_one()

    # Create School 1 and School 2
    school1 = School(
        sector_id=sector.id,
        name=f"School A {uuid.uuid4().hex[:6]}",
        code=f"SA_{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    school2 = School(
        sector_id=sector.id,
        name=f"School B {uuid.uuid4().hex[:6]}",
        code=f"SB_{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add_all([school1, school2])
    await db_session.flush()

    # Head Teacher for School 1
    head_teacher = User(
        email=f"head_{uuid.uuid4().hex[:6]}@school.rw",
        phone_e164=f"+25078{uuid.uuid4().int % 10000000:07d}",
        full_name="Head Teacher One",
        role=RoleEnum.head_teacher,
        school_id=school1.id,
        is_active=True,
    )
    # Mentor
    mentor = User(
        email=f"mentor_{uuid.uuid4().hex[:6]}@mentor.rw",
        phone_e164=f"+25078{uuid.uuid4().int % 10000000:07d}",
        full_name="Mentor Test",
        role=RoleEnum.mentor,
        sector_id=sector.id,
        is_active=True,
    )
    db_session.add_all([head_teacher, mentor])
    await db_session.flush()

    cls1 = Class(school_id=school1.id, name="P5 A", grade=5, academic_year=2026)
    cls2 = Class(school_id=school2.id, name="P5 B", grade=5, academic_year=2026)
    db_session.add_all([cls1, cls2])
    await db_session.flush()

    st1 = Student(
        school_id=school1.id,
        class_id=cls1.id,
        roll_number=1,
        full_name="Student School 1",
        status=StudentStatusEnum.active,
    )
    st2 = Student(
        school_id=school2.id,
        class_id=cls2.id,
        roll_number=1,
        full_name="Student School 2",
        status=StudentStatusEnum.active,
    )
    db_session.add_all([st1, st2])
    await db_session.flush()

    case1 = Case(
        ref=f"CAS-2026-A{uuid.uuid4().hex[:4].upper()}",
        student_id=st1.id,
        school_id=school1.id,
        status=CaseStatusEnum.open,
        level=2,
        trigger=CaseTriggerEnum.consecutive,
        risk_score=60,
        opened_at=datetime.now(UTC),
    )
    case2 = Case(
        ref=f"CAS-2026-B{uuid.uuid4().hex[:4].upper()}",
        student_id=st2.id,
        school_id=school2.id,
        status=CaseStatusEnum.open,
        level=2,
        trigger=CaseTriggerEnum.consecutive,
        risk_score=75,
        opened_at=datetime.now(UTC),
    )
    db_session.add_all([case1, case2])
    await db_session.commit()

    return {
        "school1": school1,
        "school2": school2,
        "head_teacher": head_teacher,
        "mentor": mentor,
        "case1": case1,
        "case2": case2,
    }


@pytest.mark.asyncio
async def test_cases_scoping_and_crud(
    async_client: AsyncClient,
    setup_cases_data: dict,
    db_session: AsyncSession,
):
    case1 = setup_cases_data["case1"]
    case2 = setup_cases_data["case2"]
    head_user = setup_cases_data["head_teacher"]
    mentor = setup_cases_data["mentor"]

    # 1. Admin login & sees both cases
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@garuka.rw", "password": "ChangeMe123!"},
    )
    assert login_res.status_code == 200
    admin_token = login_res.json()["access_token"]

    resp = await async_client.get(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    refs = [c["ref"] for c in resp.json()]
    assert case1.ref in refs
    assert case2.ref in refs

    # 2. Head teacher only sees case 1
    head_token = create_access_token({"sub": str(head_user.id), "role": head_user.role.value})
    resp_head = await async_client.get(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {head_token}"},
    )
    assert resp_head.status_code == 200
    head_refs = [c["ref"] for c in resp_head.json()]
    assert case1.ref in head_refs
    assert case2.ref not in head_refs

    # 3. Case detail
    resp_detail = await async_client.get(
        f"/api/v1/cases/{case1.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["ref"] == case1.ref
    assert "metrics" in detail
    assert "absence_heatmap" in detail
    assert "events" in detail

    # 4. Assign mentor
    resp_assign = await async_client.patch(
        f"/api/v1/cases/{case1.id}/assign",
        json={"mentor_id": str(mentor.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_assign.status_code == 200
    assert resp_assign.json()["mentor_id"] == str(mentor.id)

    # 5. Escalate case to Level 3
    resp_esc = await async_client.post(
        f"/api/v1/cases/{case1.id}/escalate",
        json={"to_level": 3, "note": "Parent unreachable via phone"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_esc.status_code == 200
    assert resp_esc.json()["level"] == 3
    assert resp_esc.json()["status"] == CaseStatusEnum.escalated_sector.value

    # 6. Add note
    resp_note = await async_client.post(
        f"/api/v1/cases/{case1.id}/notes",
        json={"text": "Visited sector office to check social affairs support"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_note.status_code == 200
    events = resp_note.json()["events"]
    assert any(e["type"] == "note_added" for e in events)

    # 7. Resolve case
    resp_resolve = await async_client.post(
        f"/api/v1/cases/{case1.id}/resolve",
        json={"outcome": CaseStatusEnum.resolved_returned.value, "note": "Student attended school"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_resolve.status_code == 200
    assert resp_resolve.json()["status"] == CaseStatusEnum.resolved_returned.value
    assert resp_resolve.json()["resolved_at"] is not None

    # 8. List mentors
    resp_mentors = await async_client.get(
        "/api/v1/mentors",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_mentors.status_code == 200
    mentors_list = resp_mentors.json()
    assert any(m["id"] == str(mentor.id) for m in mentors_list)
