import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.messaging import SmsOutbox, SmsStatusEnum
from app.services.sms.console_provider import ConsoleSmsProvider
from app.services.sms.outbox_worker import enqueue_sms, process_outbox_batch


@pytest.mark.asyncio
async def test_sms_deduplication(db_session: AsyncSession):
    phone = "+250780000101"
    dedupe_key = f"test_dedupe_{uuid.uuid4()}"

    # 1. First enqueue
    sms1 = await enqueue_sms(
        db=db_session,
        to_e164=phone,
        template_key="parent_absence",
        params={"child": "Mugisha"},
        body="First absence notification",
        dedupe_key=dedupe_key,
    )
    assert sms1 is not None
    await db_session.commit()

    # 2. Second enqueue with same dedupe_key should be skipped
    sms2 = await enqueue_sms(
        db=db_session,
        to_e164=phone,
        template_key="parent_absence",
        params={"child": "Mugisha"},
        body="Duplicate absence notification",
        dedupe_key=dedupe_key,
    )
    assert sms2 is None


@pytest.mark.asyncio
async def test_process_outbox_batch(db_session: AsyncSession):
    phone = "+250780000102"
    sms = await enqueue_sms(
        db=db_session,
        to_e164=phone,
        template_key="parent_visit_code",  # Exempt from quiet hours
        params={"code": "1234"},
        body="Visit code is 1234",
    )
    await db_session.commit()

    provider = ConsoleSmsProvider()
    processed = await process_outbox_batch(db_session, provider=provider)
    assert processed >= 1

    await db_session.refresh(sms)
    assert sms.status == SmsStatusEnum.sent
    assert sms.sent_at is not None
    assert sms.provider_message_id is not None


@pytest.mark.asyncio
async def test_at_sms_delivery_webhook(async_client: AsyncClient, db_session: AsyncSession):
    phone = "+250780000103"
    msg_id = f"AT_msg_{uuid.uuid4()}"

    sms = SmsOutbox(
        to_e164=phone,
        template_key="parent_absence",
        params={},
        body="Test message",
        status=SmsStatusEnum.sent,
        provider_message_id=msg_id,
    )
    db_session.add(sms)
    await db_session.commit()

    # Send delivery webhook
    resp = await async_client.post(
        f"/api/v1/webhooks/at/sms-delivery/{settings.USSD_WEBHOOK_SECRET}",
        data={
            "id": msg_id,
            "status": "Success",
            "phoneNumber": phone,
            "networkCode": "63510",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    await db_session.refresh(sms)
    assert sms.status == SmsStatusEnum.delivered
