import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.messaging import AppSetting, AuditLog, SmsOutbox, SmsStatusEnum
from app.models.user import RoleEnum, User
from sqlalchemy import delete


@pytest.mark.asyncio
async def test_get_and_patch_settings(async_client: AsyncClient, db_session: AsyncSession):
    orig_consec = settings.RULE_CONSECUTIVE_DAYS
    orig_mentor = settings.MENTOR_MAX_ACTIVE_CASES
    try:
        # 1. Login as admin
        login_res = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@garuka.rw", "password": "ChangeMe123!"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get settings
        get_res = await async_client.get("/api/v1/settings", headers=headers)
        assert get_res.status_code == 200
        data = get_res.json()
        assert "rule_consecutive_days" in data
        assert "rule_escalate_term_absences" in data
        assert "mentor_max_active_cases" in data

        # 3. Patch settings
        patch_res = await async_client.patch(
            "/api/v1/settings",
            json={"rule_consecutive_days": 4, "mentor_max_active_cases": 7},
            headers=headers,
        )
        assert patch_res.status_code == 200
        patch_data = patch_res.json()
        assert patch_data["rule_consecutive_days"] == 4
        assert patch_data["mentor_max_active_cases"] == 7

        # 4. Verify persistence
        verify_res = await async_client.get("/api/v1/settings", headers=headers)
        assert verify_res.status_code == 200
        verify_data = verify_res.json()
        assert verify_data["rule_consecutive_days"] == 4
        assert verify_data["mentor_max_active_cases"] == 7
    finally:
        settings.RULE_CONSECUTIVE_DAYS = orig_consec
        settings.MENTOR_MAX_ACTIVE_CASES = orig_mentor
        await db_session.execute(delete(AppSetting).where(AppSetting.key == "rules_thresholds"))
        await db_session.commit()


@pytest.mark.asyncio
async def test_sms_outbox_list_and_retry(async_client: AsyncClient, db_session: AsyncSession):
    # 1. Insert a failed SMS outbox record
    sms = SmsOutbox(
        to_e164="+250788123456",
        template_key="absence_alert",
        params={"student_name": "Test"},
        body="Test SMS message",
        status=SmsStatusEnum.failed,
        attempts=3,
        last_error="AT timeout",
    )
    db_session.add(sms)
    await db_session.commit()
    await db_session.refresh(sms)

    # 2. Login as admin
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@garuka.rw", "password": "ChangeMe123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. List outbox
    list_res = await async_client.get("/api/v1/sms/outbox?status=failed", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 1
    found = next((i for i in items if i["id"] == str(sms.id)), None)
    assert found is not None
    assert found["status"] == "failed"

    # 4. Retry SMS
    retry_res = await async_client.post(f"/api/v1/sms/outbox/{sms.id}/retry", headers=headers)
    assert retry_res.status_code == 200
    retried = retry_res.json()
    assert retried["status"] == "pending"
    assert retried["attempts"] == 0
    assert retried["last_error"] is None


@pytest.mark.asyncio
async def test_audit_logs_query(async_client: AsyncClient, db_session: AsyncSession):
    # 1. Insert an audit log
    audit = AuditLog(
        actor_role="admin",
        action="test.action",
        entity_type="case",
        entity_id=str(uuid.uuid4()),
        meta={"before": "open", "after": "closed"},
    )
    db_session.add(audit)
    await db_session.commit()

    # 2. Login as admin
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@garuka.rw", "password": "ChangeMe123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Query audit logs
    audit_res = await async_client.get("/api/v1/audit?action=test.action", headers=headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 1
    assert logs[0]["action"] == "test.action"
