import logging

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.messaging import SmsOutbox, SmsStatusEnum

router = APIRouter(tags=["sms-webhook"])
logger = logging.getLogger("garuka.sms.webhook")


@router.post(
    "/webhooks/at/sms-delivery/{secret}",
    summary="Africa's Talking SMS Delivery Report Webhook",
)
async def sms_delivery_callback(
    secret: str,
    id: str = Form(...),
    status: str = Form(...),
    phoneNumber: str | None = Form(None),
    networkCode: str | None = Form(None),
    failureReason: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    if secret != settings.USSD_WEBHOOK_SECRET:
        logger.warning("Invalid secret on SMS delivery webhook attempt: %s", secret)
        raise HTTPException(status_code=401, detail="Unauthorized")

    logger.info("Received AT SMS delivery report: msg_id=%s status=%s", id, status)

    res = await db.execute(select(SmsOutbox).where(SmsOutbox.provider_message_id == id))
    sms = res.scalar_one_or_none()
    if not sms:
        logger.info("No matching SMS found for provider_message_id=%s", id)
        return {"status": "ignored", "reason": "not_found"}

    norm_status = status.lower()
    if norm_status in ("success", "sent", "delivered"):
        sms.status = SmsStatusEnum.delivered
    elif norm_status in ("failed", "rejected"):
        sms.status = SmsStatusEnum.failed
        sms.last_error = failureReason or status

    await db.commit()
    return {"status": "ok", "sms_id": str(sms.id)}
