import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_login_success(async_client: AsyncClient):
    payload = {
        "email": "admin@garuka.rw",
        "password": "ChangeMe123!",
    }
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "admin@garuka.rw"
    assert data["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_login_invalid_password(async_client: AsyncClient):
    payload = {
        "email": "admin@garuka.rw",
        "password": "WrongPassword!",
    }
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_endpoint(async_client: AsyncClient):
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "head@gsdemo1.rw", "password": "ChangeMe123!"},
    )
    token = login_res.json()["access_token"]

    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "head_teacher"
    assert data["email"] == "head@gsdemo1.rw"
    # Verify phone number masking for privacy
    assert "****" in data["phone_masked"]


@pytest.mark.asyncio
async def test_token_refresh(async_client: AsyncClient):
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@garuka.rw", "password": "ChangeMe123!"},
    )
    refresh_token = login_res.json()["refresh_token"]

    response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
