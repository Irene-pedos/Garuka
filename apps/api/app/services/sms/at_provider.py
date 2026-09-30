import logging

import httpx

from app.core.config import settings
from app.core.logging import mask_phone
from app.services.sms.provider import SmsProvider

logger = logging.getLogger("garuka.sms.africastalking")


class AfricasTalkingSmsProvider(SmsProvider):
    def __init__(self):
        self.username = settings.AT_USERNAME
        self.api_key = settings.AT_API_KEY
        self.sender_id = settings.AT_SENDER_ID or None

        if self.username == "sandbox":
            self.endpoint = "https://api.sandbox.africastalking.com/version1/messaging"
        else:
            self.endpoint = "https://api.africastalking.com/version1/messaging"

    async def send_sms(self, to_e164: str, message: str) -> str:
        headers = {
            "apiKey": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "username": self.username,
            "to": to_e164,
            "message": message,
        }
        if self.sender_id:
            data["from"] = self.sender_id

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(self.endpoint, headers=headers, data=data)
                response.raise_for_status()
                res_json = response.json()
                recipients = res_json.get("SMSMessageData", {}).get("Recipients", [])
                if recipients:
                    msg_id = recipients[0].get("messageId", "")
                    logger.info("AT SMS sent to %s, messageId=%s", mask_phone(to_e164), msg_id)
                    return msg_id
                return "at_success_no_id"
            except Exception as e:
                logger.error("Failed to send AT SMS to %s: %s", mask_phone(to_e164), str(e))
                raise
