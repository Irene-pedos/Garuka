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


@pytest.mark.asyncio
async def test_update_profile_and_credentials(async_client: AsyncClient):
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "head@gsdemo1.rw", "password": "ChangeMe123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Update Profile (name, language, phone)
    patch_res = await async_client.patch(
        "/api/v1/auth/me",
        json={
            "full_name": "Head Teacher Updated",
            "language": "en",
            "phone_e164": "+250788100999",
            "avatar_url": "data:image/svg+xml;utf8,<svg></svg>",
        },
        headers=headers,
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["full_name"] == "Head Teacher Updated"
    assert data["language"] == "en"
    assert data["phone_e164"] == "+250788100999"
    assert data["avatar_url"] == "data:image/svg+xml;utf8,<svg></svg>"

    # 2. Change PIN (4 digits)
    pin_res = await async_client.post(
        "/api/v1/auth/change-pin",
        json={"current_pin": "4821", "new_pin": "9999"},
        headers=headers,
    )
    assert pin_res.status_code == 200
    assert pin_res.json()["status"] == "ok"

    # Reset PIN back for other tests
    await async_client.post(
        "/api/v1/auth/change-pin",
        json={"current_pin": "9999", "new_pin": "4821"},
        headers=headers,
    )

    # 3. Change Password
    pwd_res = await async_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "ChangeMe123!", "new_password": "NewSecretPassword123!"},
        headers=headers,
    )
    assert pwd_res.status_code == 200

    # Reset Password back for other tests
    await async_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "NewSecretPassword123!", "new_password": "ChangeMe123!"},
        headers=headers,
    )

    # 4. Upload Avatar (with realistic payload over 10KB to verify TEXT storage)
    large_image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"A" * 10240
    files = {"file": ("avatar.png", large_image_bytes, "image/png")}
    avatar_res = await async_client.post(
        "/api/v1/auth/avatar",
        files=files,
        headers=headers,
    )
    assert avatar_res.status_code == 200
    assert "data:image/png;base64" in avatar_res.json()["avatar_url"]
    assert len(avatar_res.json()["avatar_url"]) > 500


@pytest.mark.asyncio
async def test_auth_via_query_token(async_client: AsyncClient):
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@garuka.rw", "password": "ChangeMe123!"},
    )
    token = login_res.json()["access_token"]

    # Request without Authorization header but with token in query params
    res = await async_client.get(f"/api/v1/auth/me?token={token}")
    assert res.status_code == 200
    assert res.json()["email"] == "admin@garuka.rw"

