import logging

from fastapi import APIRouter, Form, Response
from fastapi.responses import PlainTextResponse

from app.core.config import settings
from app.core.logging import hash_phone
from app.services.ussd.render import USSDLengthExceededError, render_ussd_response

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

        # M0 Milestone: Return 'CON Hello Garuka'
        response_body = render_ussd_response("CON", "Hello Garuka")
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
