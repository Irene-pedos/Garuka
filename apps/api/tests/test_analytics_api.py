import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import School, Sector
from app.models.student import Class, Student, StudentStatusEnum
from app.models.user import RoleEnum, User


@pytest.mark.asyncio
async def test_analytics_overview_and_scoping(async_client: AsyncClient, db_session: AsyncSession):
    # 1. Login as admin
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@garuka.rw", "password": "ChangeMe123!"},
    )
    admin_token = login_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Call overview endpoint
    res = await async_client.get("/api/v1/analytics/overview", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()

    assert "scope" in data
    assert "kpis" in data
    assert "cases_by_level" in data
    assert "students_active" in data["kpis"]
    assert "open_cases" in data["kpis"]
    assert "attendance_compliance_pct" in data["kpis"]
    assert isinstance(data["cases_by_level"], dict)
    assert "attendance_trend" in data
    assert isinstance(data["attendance_trend"], list)


@pytest.mark.asyncio
async def test_analytics_trends_endpoint(async_client: AsyncClient, db_session: AsyncSession):
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@garuka.rw", "password": "ChangeMe123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = await async_client.get("/api/v1/analytics/trends?days=30", headers=headers)
    assert res.status_code == 200
    trends = res.json()
    assert isinstance(trends, list)
    if trends:
        item = trends[0]
        assert "date" in item
        assert "present" in item
        assert "absent" in item
        assert "enrolled" in item
        assert "cases" in item


@pytest.mark.asyncio
async def test_schools_compare_endpoint(async_client: AsyncClient, db_session: AsyncSession):
    # Login as admin
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@garuka.rw", "password": "ChangeMe123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Call schools-compare
    res = await async_client.get("/api/v1/analytics/schools-compare", headers=headers)
    assert res.status_code == 200
    schools = res.json()
    assert isinstance(schools, list)
    if schools:
        s0 = schools[0]
        assert "school_name" in s0
        assert "students_active" in s0
        assert "open_cases" in s0
        assert "attendance_compliance_pct" in s0
