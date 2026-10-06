import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_ussd_valid_request(async_client: AsyncClient):
    payload = {
        "sessionId": f"ATUid_test_{uuid.uuid4().hex[:8]}",
        "serviceCode": "*384*1234#",
        "phoneNumber": "+250736200001",
        "networkCode": "99999",
        "text": "",
    }
    response = await async_client.post(
        f"/api/v1/ussd/{settings.USSD_WEBHOOK_SECRET}",
        data=payload,
    )
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert response.text.startswith("CON ")


@pytest.mark.asyncio
async def test_ussd_invalid_secret_returns_200_end(async_client: AsyncClient):
    payload = {
        "sessionId": "ATUid_bad_secret",
        "serviceCode": "*384*1234#",
        "phoneNumber": "+250736200001",
        "networkCode": "99999",
        "text": "",
    }
    response = await async_client.post(
        "/api/v1/ussd/wrong-secret",
        data=payload,
    )
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert response.text == "END Not available."


@pytest.mark.asyncio
async def test_ussd_exception_trapped_as_200_service_unavailable(async_client: AsyncClient):
    payload = {
        "sessionId": "ATUid_crash_test",
        "serviceCode": "*384*1234#",
        "phoneNumber": "+250736200001",
        "networkCode": "99999",
        "text": "",
    }
    with patch(
        "app.api.v1.ussd_webhook.handle_ussd_request", side_effect=RuntimeError("Simulated crash")
    ):
        response = await async_client.post(
            f"/api/v1/ussd/{settings.USSD_WEBHOOK_SECRET}",
            data=payload,
        )
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert response.text == "END Service temporarily unavailable. Please try again."


@pytest.mark.asyncio
async def test_ussd_dependency_failure_trapped_as_200(async_client: AsyncClient):
    """Test that a failure in dependency resolution (e.g. database down) is trapped
    by the outer ASGI middleware and returns HTTP 200 with text/plain."""
    from app.db.session import get_db
    from app.main import app

    async def broken_get_db():
        raise ConnectionError("Database cluster unreachable")
        yield  # noqa: unreachable

    app.dependency_overrides[get_db] = broken_get_db
    try:
        payload = {
            "sessionId": "ATUid_db_fail_test",
            "serviceCode": "*384*1234#",
            "phoneNumber": "+250736200001",
            "networkCode": "99999",
            "text": "",
        }
        response = await async_client.post(
            f"/api/v1/ussd/{settings.USSD_WEBHOOK_SECRET}",
            data=payload,
        )
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert response.text == "END Service temporarily unavailable. Please try again."
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_ussd_ip_allowlist_enforcement(async_client: AsyncClient):
    """Test that AT_ALLOWED_IPS rejects unauthorized IPs and accepts allowed ones."""
    payload = {
        "sessionId": f"ATUid_ip_{uuid.uuid4().hex[:6]}",
        "serviceCode": "*384*1234#",
        "phoneNumber": "+250736200001",
        "networkCode": "99999",
        "text": "",
    }
    with patch.object(settings, "AT_ALLOWED_IPS", "196.201.214.1, 196.201.214.2"):
        # 1. Request from unauthorized IP
        bad_res = await async_client.post(
            f"/api/v1/ussd/{settings.USSD_WEBHOOK_SECRET}",
            data=payload,
            headers={"X-Forwarded-For": "10.0.0.99"},
        )
        assert bad_res.status_code == 200
        assert bad_res.text == "END Not available."

        # 2. Request from authorized IP
        good_res = await async_client.post(
            f"/api/v1/ussd/{settings.USSD_WEBHOOK_SECRET}",
            data=payload,
            headers={"X-Forwarded-For": "196.201.214.1"},
        )
        assert good_res.status_code == 200
        assert good_res.text.startswith("CON ")


@pytest.mark.asyncio
async def test_dev_ussd_simulator_exception_trapped(async_client: AsyncClient):
    """Test that the dev USSD simulator also catches exceptions and returns HTTP 200 PlainText."""
    with patch(
        "app.api.v1.ussd_webhook.handle_ussd_request",
        side_effect=RuntimeError("Dev simulator failure"),
    ):
        response = await async_client.post(
            "/api/v1/dev/ussd",
            json={"phoneNumber": "+250780000001", "text": ""},
        )
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert response.text == "END Service temporarily unavailable. Please try again."

