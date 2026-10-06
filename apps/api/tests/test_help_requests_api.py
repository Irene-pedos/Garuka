import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import BarrierCodeEnum, HelpRequest, HelpRequestStatusEnum
from app.models.geo import School, Sector
from app.models.student import Class, ConsentSourceEnum, Guardian, Student, StudentStatusEnum, student_guardians
from app.models.user import RoleEnum, User


@pytest.mark.asyncio
async def test_help_request_crud_and_scoping(async_client: AsyncClient, db_session: AsyncSession):
    # 1. Setup school, class, student, guardian
    sector_res = await db_session.execute(select(Sector).limit(1))
    sector = sector_res.scalar_one()

    school = School(
        sector_id=sector.id,
        name=f"Help School {uuid.uuid4().hex[:6]}",
        code=f"HS_{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(school)
    await db_session.flush()

    cls = Class(school_id=school.id, name="P5 H", grade=5, academic_year=2026)
    db_session.add(cls)
    await db_session.flush()

    student = Student(
        school_id=school.id,
        class_id=cls.id,
        roll_number=1,
        full_name="Alice Help",
        status=StudentStatusEnum.active,
    )
    db_session.add(student)
    await db_session.flush()

    guardian = Guardian(
        full_name="Alice Guardian",
        phone_e164=f"+25078{uuid.uuid4().int % 10000000:07d}",
    )
    db_session.add(guardian)
    await db_session.flush()

    await db_session.execute(
        student_guardians.insert().values(
            student_id=student.id,
            guardian_id=guardian.id,
            relationship="mother",
            is_primary=True,
        )
    )
    await db_session.commit()

    # 2. Login as admin
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@garuka.rw", "password": "ChangeMe123!"},
    )
    admin_token = login_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Create help request via API with authorized guardian
    create_res = await async_client.post(
        "/api/v1/help-requests",
        json={
            "student_id": str(student.id),
            "guardian_id": str(guardian.id),
            "barrier_code": "COST",
            "consent": True,
        },
        headers=admin_headers,
    )
    assert create_res.status_code == 201
    hr_data = create_res.json()
    assert hr_data["student_name"] == "Alice Help"
    assert hr_data["barrier_code"] == "COST"
    assert hr_data["status"] == "new"
    hr_id = hr_data["id"]

    # Verify consent was recorded
    await db_session.refresh(guardian)
    assert guardian.consent_at is not None
    assert guardian.consent_source == ConsentSourceEnum.dashboard

    # 4. List help requests as admin
    list_res = await async_client.get("/api/v1/help-requests", headers=admin_headers)
    assert list_res.status_code == 200
    assert any(item["id"] == hr_id for item in list_res.json())

    # 5. Update help request status
    update_res = await async_client.patch(
        f"/api/v1/help-requests/{hr_id}",
        json={"status": "in_progress"},
        headers=admin_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_help_request_unauthorized_guardian_rejected(async_client: AsyncClient, db_session: AsyncSession):
    # Setup student and an unrelated guardian
    sector_res = await db_session.execute(select(Sector).limit(1))
    sector = sector_res.scalar_one()

    school = School(
        sector_id=sector.id,
        name=f"Help School 2 {uuid.uuid4().hex[:6]}",
        code=f"HS2_{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(school)
    await db_session.flush()

    cls = Class(school_id=school.id, name="P4 H2", grade=4, academic_year=2026)
    db_session.add(cls)
    await db_session.flush()

    student = Student(
        school_id=school.id,
        class_id=cls.id,
        roll_number=2,
        full_name="Bob Help",
        status=StudentStatusEnum.active,
    )
    db_session.add(student)

    unrelated_guardian = Guardian(
        full_name="Unrelated Parent",
        phone_e164=f"+25078{uuid.uuid4().int % 10000000:07d}",
    )
    db_session.add(unrelated_guardian)
    await db_session.commit()

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@garuka.rw", "password": "ChangeMe123!"},
    )
    admin_token = login_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Creating help request with an unlinked guardian must return 403
    create_res = await async_client.post(
        "/api/v1/help-requests",
        json={
            "student_id": str(student.id),
            "guardian_id": str(unrelated_guardian.id),
            "barrier_code": "HUNGER",
        },
        headers=admin_headers,
    )
    assert create_res.status_code == 403
    assert "not authorized" in create_res.json()["detail"].lower()
