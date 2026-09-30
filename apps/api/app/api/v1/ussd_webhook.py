import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import hash_phone
from app.db.session import get_db
from app.services.ussd.engine import handle_ussd_request
from app.services.ussd.render import USSDLengthExceededError

router = APIRouter(tags=["ussd"])
logger = logging.getLogger("garuka.ussd")

SERVICE_UNAVAILABLE_BODY = "END Service temporarily unavailable. Please try again."
NOT_AVAILABLE_BODY = "END Not available."


@router.post(
    "/ussd/{secret}",
    response_class=PlainTextResponse,
    operation_id="handle_ussd_callback",
    summary="Africa's Talking USSD Webhook",
)
async def ussd_callback(
    secret: str,
    sessionId: str = Form(""),
    serviceCode: str = Form(""),
    phoneNumber: str = Form(""),
    networkCode: str = Form(""),
    text: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    USSD Webhook handler for Africa's Talking.
    Always returns HTTP 200 with text/plain, starting with CON or END.
    Never logs raw PINs or raw cumulative text.
    """
    try:
        # 1. Validate Secret Path Segment
        if secret != settings.USSD_WEBHOOK_SECRET:
            logger.warning(
                "Unauthorized USSD webhook attempt: invalid secret. phone_hash=%s",
                hash_phone(phoneNumber),
            )
            return PlainTextResponse(
                NOT_AVAILABLE_BODY,
                status_code=200,
                media_type="text/plain; charset=utf-8",
            )

        logger.info(
            "USSD request received. session_id=%s phone_hash=%s text_len=%d",
            sessionId,
            hash_phone(phoneNumber),
            len(text),
        )

        _, response_body = await handle_ussd_request(
            session_id=sessionId,
            service_code=serviceCode,
            phone_number=phoneNumber,
            raw_text=text,
            db=db,
        )

        return PlainTextResponse(
            response_body,
            status_code=200,
            media_type="text/plain; charset=utf-8",
        )

    except USSDLengthExceededError as e:
        logger.error("USSD screen exceeded character limit: %s", str(e))
        return PlainTextResponse(
            SERVICE_UNAVAILABLE_BODY,
            status_code=200,
            media_type="text/plain; charset=utf-8",
        )
    except Exception as e:
        logger.exception("Unexpected error in USSD handler: %s", type(e).__name__)
        return PlainTextResponse(
            SERVICE_UNAVAILABLE_BODY,
            status_code=200,
            media_type="text/plain; charset=utf-8",
        )


class DevUssdRequest(BaseModel):
    phoneNumber: str
    text: str = ""
    sessionId: str = "dev-session-1"
    serviceCode: str | None = "*384*1234#"


@router.post(
    "/dev/ussd",
    response_class=PlainTextResponse,
    operation_id="dev_ussd_simulator",
    summary="Dev USSD Simulator endpoint",
)
async def dev_ussd_simulator(
    payload: DevUssdRequest,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Dev-only USSD endpoint simulating Africa's Talking webhook."""
    if settings.APP_ENV == "production":
        raise HTTPException(status_code=404, detail="Not available in production")

    _, response_body = await handle_ussd_request(
        session_id=payload.sessionId,
        service_code=payload.serviceCode or "*384*1234#",
        phone_number=payload.phoneNumber,
        raw_text=payload.text,
        db=db,
    )

    return PlainTextResponse(
        response_body,
        status_code=200,
        media_type="text/plain; charset=utf-8",
    )
