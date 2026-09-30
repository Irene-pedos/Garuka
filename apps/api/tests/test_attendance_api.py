import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.student import Class, Student
from app.models.user import RoleEnum, User
from app.services.ussd.calendar_helper import get_kigali_today


@pytest.fixture
async def head_teacher_token(async_client: AsyncClient) -> str:
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "head@gsdemo1.rw", "password": "ChangeMe123!"},
    )
    return login_res.json()["access_token"]




@pytest.fixture
async def p5_class(db_session: AsyncSession) -> Class:
    res = await db_session.execute(select(Class).where(Class.name == "P5 A").limit(1))
    return res.scalar_one()


@pytest.mark.asyncio
async def test_get_class_attendance(
    async_client: AsyncClient,
    head_teacher_token: str,
    p5_class: Class,
):
    headers = {"Authorization": f"Bearer {head_teacher_token}"}
    today = get_kigali_today()
    resp = await async_client.get(
        f"/api/v1/classes/{p5_class.id}/attendance?date={today.isoformat()}",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["class_id"] == str(p5_class.id)
    assert data["class_name"] == p5_class.name
    assert isinstance(data["students"], list)
    assert len(data["students"]) > 0


@pytest.mark.asyncio
async def test_submit_class_attendance_and_void(
    async_client: AsyncClient,
    db_session: AsyncSession,
    head_teacher_token: str,
    p5_class: Class,
):
    headers = {"Authorization": f"Bearer {head_teacher_token}"}
    today = get_kigali_today()

    # Get students of P5 A
    students_res = await db_session.execute(
        select(Student).where(Student.class_id == p5_class.id).limit(3)
    )
    students = students_res.scalars().all()
    absent_ids = [str(s.id) for s in students[:2]]

    # 1. Submit attendance with 2 absent students
    resp = await async_client.post(
        f"/api/v1/classes/{p5_class.id}/attendance",
        headers=headers,
        json={
            "date": today.isoformat(),
            "absent_student_ids": absent_ids,
        },
    )
    assert resp.status_code == 200
    sub_data = resp.json()
    assert sub_data["absent_count"] == 2
    assert sub_data["source"] == "dashboard"

    # 2. Get class attendance and verify absence details
    get_resp = await async_client.get(
        f"/api/v1/classes/{p5_class.id}/attendance?date={today.isoformat()}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    att_data = get_resp.json()
    absent_items = [st for st in att_data["students"] if st["is_absent"]]
    assert len(absent_items) == 2
    absence_id = absent_items[0]["absence_id"]
    assert absence_id is not None

    # 3. Void one absence
    void_resp = await async_client.delete(
        f"/api/v1/absences/{absence_id}",
        headers=headers,
    )
    assert void_resp.status_code == 200
    assert void_resp.json()["status"] == "voided"


@pytest.mark.asyncio
async def test_get_attendance_compliance_grid(
    async_client: AsyncClient,
    head_teacher_token: str,
    p5_class: Class,
):
    headers = {"Authorization": f"Bearer {head_teacher_token}"}
    resp = await async_client.get(
        f"/api/v1/attendance/compliance?school_id={p5_class.school_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["school_id"] == str(p5_class.school_id)
    assert "compliance_pct" in data
    assert len(data["classes"]) >= 1
    assert len(data["classes"][0]["days"]) > 0

    # Test CSV export
    csv_resp = await async_client.get(
        f"/api/v1/attendance/compliance?school_id={p5_class.school_id}&format=csv",
        headers=headers,
    )
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "Class,Grade,Date,Status,AbsentCount" in csv_resp.text
