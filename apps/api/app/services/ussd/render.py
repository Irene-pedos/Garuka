"""USSD Screen Renderer & Character Limit Enforcement."""

MAX_USSD_LENGTH = 182
TARGET_USSD_LENGTH = 160


class USSDLengthExceededError(ValueError):
    """Raised when a rendered USSD response exceeds the protocol maximum."""


def render_ussd_response(kind: str, body: str) -> str:
    """
    Renders standard USSD payload for Africa's Talking gateway.
    kind must be 'CON' or 'END'.
    Ensures body starts with prefix and strictly validates length <= 182 chars.
    """
    kind = kind.upper().strip()
    if kind not in ("CON", "END"):
        raise ValueError(f"Invalid USSD response kind: '{kind}'. Must be 'CON' or 'END'.")

    formatted = f"{kind} {body}"
    length = len(formatted)
    if length > MAX_USSD_LENGTH:
        raise USSDLengthExceededError(
            f"USSD screen length {length} exceeds hard limit {MAX_USSD_LENGTH}: {formatted[:50]}..."
        )
    return formatted
