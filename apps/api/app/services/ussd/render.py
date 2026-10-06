"""USSD Screen Renderer & Character Limit Enforcement.

Per SPEC section 0 rule 3 and AGENTS.md rule 3, every USSD screen MUST be ≤ 160 characters.
The AT protocol hard-kills sessions above 182 characters.

render_ussd_response enforces TARGET_USSD_LENGTH (160) by default.
Pass allow_long=True only for screens that cannot be shortened and are still below
MAX_USSD_LENGTH (182). All such call sites must include a comment explaining the exception.
"""

MAX_USSD_LENGTH = 182
TARGET_USSD_LENGTH = 160


class USSDLengthExceededError(ValueError):
    """Raised when a rendered USSD response exceeds the allowed character limit."""


def render_ussd_response(kind: str, body: str, *, allow_long: bool = False) -> str:
    """
    Renders a standard USSD payload for the Africa's Talking gateway.

    Args:
        kind: 'CON' (session continues) or 'END' (terminal screen).
        body: The screen body text (newlines allowed, no leading prefix).
        allow_long: If True, accept up to MAX_USSD_LENGTH (182) instead of
                    TARGET_USSD_LENGTH (160). Use only when the screen cannot
                    be shortened and must stay below the AT hard limit.

    Returns:
        The full USSD string, e.g. "CON Welcome\n1. Option".

    Raises:
        ValueError: If kind is not 'CON' or 'END'.
        USSDLengthExceededError: If the formatted string exceeds the active limit.
    """
    kind = kind.upper().strip()
    if kind not in ("CON", "END"):
        raise ValueError(f"Invalid USSD response kind: '{kind}'. Must be 'CON' or 'END'.")

    formatted = f"{kind} {body}"
    length = len(formatted)
    limit = MAX_USSD_LENGTH if allow_long else TARGET_USSD_LENGTH

    if length > limit:
        label = "hard limit" if allow_long else "target limit"
        raise USSDLengthExceededError(
            f"USSD screen length {length} exceeds {label} {limit}: '{formatted[:50]}...'"
        )
    return formatted
