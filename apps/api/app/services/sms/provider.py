from abc import ABC, abstractmethod


class SmsProvider(ABC):
    @abstractmethod
    async def send_sms(self, to_e164: str, message: str) -> str:
        """
        Sends an SMS message to an E.164 phone number.
        Returns provider message ID.
        """
