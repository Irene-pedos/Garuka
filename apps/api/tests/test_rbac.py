import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(async_client: AsyncClient):
    response = await async_client.get("/api/v1/districts")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_full_access(async_client: AsyncClient):
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@garuka.rw", "password": "ChangeMe123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    dist_res = await async_client.get("/api/v1/districts", headers=headers)
    assert dist_res.status_code == 200
    assert len(dist_res.json()) >= 1

    schools_res = await async_client.get("/api/v1/schools", headers=headers)
    assert schools_res.status_code == 200
    assert len(schools_res.json()) >= 1


@pytest.mark.asyncio
async def test_head_teacher_scope_enforcement(async_client: AsyncClient):
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "head@gsdemo1.rw", "password": "ChangeMe123!"},
    )
    token = login_res.json()["access_token"]
    head_user = login_res.json()["user"]
    headers = {"Authorization": f"Bearer {token}"}

    # Head teacher querying /schools only sees their own school
    schools_res = await async_client.get("/api/v1/schools", headers=headers)
    assert schools_res.status_code == 200
    schools = schools_res.json()
    assert len(schools) == 1
    assert schools[0]["id"] == head_user["school_id"]

    # Head teacher cannot create class in another random school
    fake_school_id = str(uuid.uuid4())
    create_class_res = await async_client.post(
        f"/api/v1/schools/{fake_school_id}/classes",
        json={"name": "P1 A", "grade": 1, "academic_year": 2026},
        headers=headers,
    )
    assert create_class_res.status_code == 403
