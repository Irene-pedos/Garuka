import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import School
from app.models.student import Class
from app.models.user import RoleEnum, User


@pytest.mark.asyncio
async def test_head_teacher_user_flow(async_client: AsyncClient, db_session: AsyncSession):
    # 1. Login as head teacher (head@gsdemo1.rw)
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "head@gsdemo1.rw", "password": "ChangeMe123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    head_user = login_res.json()["user"]
    school_id = head_user["school_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch classes in this school
    classes_res = await db_session.execute(
        select(Class).where(Class.school_id == school_id).order_by(Class.name)
    )
    school_classes = classes_res.scalars().all()
    assert len(school_classes) >= 1
    class_p5 = school_classes[0]

    # 2. Head teacher registers a new teacher with class assignment
    teacher_phone = f"+25078{uuid.uuid4().int % 10000000:07d}"
    create_payload = {
        "full_name": "Jean Bosco Test",
        "phone_e164": teacher_phone,
        "email": f"jean_test_{uuid.uuid4().hex[:6]}@example.com",
        "role": "teacher",
        "school_id": str(school_id),
        "class_ids": [str(class_p5.id)],
    }
    create_res = await async_client.post("/api/v1/users", json=create_payload, headers=headers)
    assert create_res.status_code == 201, create_res.text
    new_teacher = create_res.json()
    assert new_teacher["full_name"] == "Jean Bosco Test"
    assert new_teacher["role"] == "teacher"
    assert len(new_teacher["assigned_classes"]) == 1
    assert new_teacher["assigned_classes"][0]["id"] == str(class_p5.id)

    teacher_id = new_teacher["id"]

    # 3. Head teacher lists users and verifies assigned class is present
    list_res = await async_client.get("/api/v1/users", headers=headers)
    assert list_res.status_code == 200
    users_list = list_res.json()
    created_item = next((u for u in users_list if u["id"] == teacher_id), None)
    assert created_item is not None
    assert len(created_item["assigned_classes"]) == 1
    assert created_item["assigned_classes"][0]["name"] == class_p5.name

    # 4. Update teacher details & class assignment
    update_res = await async_client.patch(
        f"/api/v1/users/{teacher_id}",
        json={"full_name": "Jean Bosco Updated", "class_ids": []},
        headers=headers,
    )
    assert update_res.status_code == 200
    updated_teacher = update_res.json()
    assert updated_teacher["full_name"] == "Jean Bosco Updated"
    assert len(updated_teacher["assigned_classes"]) == 0

    # 5. Reset teacher PIN
    reset_res = await async_client.post(f"/api/v1/users/{teacher_id}/reset-pin", headers=headers)
    assert reset_res.status_code == 200
    assert "PIN reset successfully" in reset_res.json()["message"]


@pytest.mark.asyncio
async def test_head_teacher_scoping_restrictions(async_client: AsyncClient, db_session: AsyncSession):
    # Login as head teacher
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "head@gsdemo1.rw", "password": "ChangeMe123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Cannot create a non-teacher role (e.g. mentor or admin)
    res_bad_role = await async_client.post(
        "/api/v1/users",
        json={
            "full_name": "Invalid Mentor",
            "phone_e164": "+250789999001",
            "role": "mentor",
        },
        headers=headers,
    )
    assert res_bad_role.status_code == 403

    # Cannot assign a class that belongs to another school
    fake_class_id = str(uuid.uuid4())
    res_bad_class = await async_client.post(
        "/api/v1/users",
        json={
            "full_name": "Bad Class Teacher",
            "phone_e164": f"+25078{uuid.uuid4().int % 10000000:07d}",
            "role": "teacher",
            "class_ids": [fake_class_id],
        },
        headers=headers,
    )
    assert res_bad_class.status_code == 400
