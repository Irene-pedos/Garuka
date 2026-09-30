import hashlib
import logging
import re

from app.core.config import settings

logger = logging.getLogger("garuka")


def mask_phone(phone: str) -> str:
    """Mask phone number e.g. +250788123456 -> +25078****456."""
    if not phone or len(phone) < 8:
        return "****"
    return f"{phone[:6]}****{phone[-3:]}"


def hash_phone(phone: str) -> str:
    """Hash phone number using SHA-256 for privacy in logs/audit."""
    if not phone:
        return ""
    return hashlib.sha256(phone.encode("utf-8")).hexdigest()[:16]


class SanitizeLogFilter(logging.Filter):
    """
    Log filter ensuring no raw USSD 'text' with PINs or plain PIN digits are logged.
    """

    PIN_PATTERN = re.compile(r"\b\d{4}\b")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str) and (
            "pin=" in record.msg.lower() or "pin:" in record.msg.lower()
        ):
            record.msg = re.sub(r"(pin[=:]\s*)\d+", r"\1****", record.msg, flags=re.IGNORECASE)
        return True


def setup_logging():
    logging.basicConfig(
        level=logging.INFO if settings.APP_ENV != "development" else logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    root_logger = logging.getLogger()
    root_logger.addFilter(SanitizeLogFilter())
