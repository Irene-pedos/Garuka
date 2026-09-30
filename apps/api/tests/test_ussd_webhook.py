from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_ussd_valid_request(async_client: AsyncClient):
    payload = {
        "sessionId": "ATUid_test_session_1",
        "serviceCode": "*384*1234#",
        "phoneNumber": "+250780000001",
        "networkCode": "99999",
        "text": "",
    }
    response = await async_client.post(
        f"/api/v1/ussd/{settings.USSD_WEBHOOK_SECRET}",
        data=payload,
    )
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert response.text == "CON Hello Garuka"


@pytest.mark.asyncio
async def test_ussd_invalid_secret_returns_200_end(async_client: AsyncClient):
    payload = {
        "sessionId": "ATUid_bad_secret",
        "serviceCode": "*384*1234#",
        "phoneNumber": "+250780000001",
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
        "phoneNumber": "+250780000001",
        "networkCode": "99999",
        "text": "",
    }
    with patch("app.api.v1.ussd_webhook.render_ussd_response", side_effect=RuntimeError("Simulated crash")):
        response = await async_client.post(
            f"/api/v1/ussd/{settings.USSD_WEBHOOK_SECRET}",
            data=payload,
        )
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert response.text == "END Service temporarily unavailable. Please try again."
