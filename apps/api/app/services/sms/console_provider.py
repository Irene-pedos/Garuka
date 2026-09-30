import logging
import uuid

from app.core.logging import mask_phone
from app.services.sms.provider import SmsProvider

logger = logging.getLogger("garuka.sms.console")


class ConsoleSmsProvider(SmsProvider):
    async def send_sms(self, to_e164: str, message: str) -> str:
        mock_id = f"console_{uuid.uuid4().hex[:12]}"
        logger.info(
            "[ConsoleSMS] TO: %s | ID: %s | BODY: %s",
            mask_phone(to_e164),
            mock_id,
            message,
        )
        return mock_id
