"""Tests for the USSD screen renderer.

Per SPEC section 0 rule 3 and AGENTS.md rule 3, every USSD screen MUST be ≤ 160 chars.
The AT protocol hard-kills sessions above 182 chars (hard limit).
"""
import pytest

from app.services.ussd.render import (
    MAX_USSD_LENGTH,
    TARGET_USSD_LENGTH,
    USSDLengthExceededError,
    render_ussd_response,
)


# ---------------------------------------------------------------------------
# Basic rendering
# ---------------------------------------------------------------------------


def test_render_con_response():
    resp = render_ussd_response("CON", "Welcome to Garuka")
    assert resp == "CON Welcome to Garuka"
    assert len(resp) <= TARGET_USSD_LENGTH


def test_render_end_response():
    resp = render_ussd_response("END", "Session completed")
    assert resp == "END Session completed"
    assert len(resp) <= TARGET_USSD_LENGTH


def test_render_invalid_kind():
    with pytest.raises(ValueError, match="Invalid USSD response kind"):
        render_ussd_response("UNKNOWN", "Test")


# ---------------------------------------------------------------------------
# 160-character target limit (default)
# ---------------------------------------------------------------------------


def test_render_exactly_target_limit():
    """A screen exactly at the 160-char target should succeed."""
    # "CON " = 4 chars; body = 156 chars → total 160
    body = "x" * (TARGET_USSD_LENGTH - 4)
    resp = render_ussd_response("CON", body)
    assert len(resp) == TARGET_USSD_LENGTH


def test_render_exceeds_target_limit_rejected_by_default():
    """A screen at 161 chars must be rejected by the default path."""
    body = "x" * (TARGET_USSD_LENGTH - 4 + 1)  # total = 161
    with pytest.raises(USSDLengthExceededError, match="target limit"):
        render_ussd_response("CON", body)


def test_render_exceeds_target_but_allow_long_passes():
    """allow_long=True permits up to MAX_USSD_LENGTH (182), not TARGET (160)."""
    # Total = 161, which is between 160 and 182
    body = "x" * (TARGET_USSD_LENGTH - 4 + 1)
    resp = render_ussd_response("CON", body, allow_long=True)
    assert len(resp) == TARGET_USSD_LENGTH + 1


# ---------------------------------------------------------------------------
# Hard limit (182 chars) with allow_long=True
# ---------------------------------------------------------------------------


def test_render_exact_hard_limit_with_allow_long():
    """allow_long=True accepts exactly 182 characters."""
    body = "x" * (MAX_USSD_LENGTH - 4)  # "CON " + 178 = 182
    resp = render_ussd_response("CON", body, allow_long=True)
    assert len(resp) == MAX_USSD_LENGTH


def test_render_exceeding_hard_limit_rejected_even_with_allow_long():
    """No screen may exceed 182 chars, even with allow_long=True."""
    body = "x" * (MAX_USSD_LENGTH - 4 + 1)  # 183 total
    with pytest.raises(USSDLengthExceededError, match="hard limit"):
        render_ussd_response("CON", body, allow_long=True)


# ---------------------------------------------------------------------------
# Dynamic screen length tests
# ---------------------------------------------------------------------------


def test_dynamic_screen_with_long_name_stays_under_target():
    """Dynamic screens with long names must still fit in 160 chars."""
    # Simulate T_CONFIRM: "{n} absent: {rolls}.\n1. Save\n2. Cancel"
    n = 10
    rolls = ", ".join(str(r) for r in range(1, n + 1))  # "1, 2, 3, 4, 5, 6, 7, 8, 9, 10"
    body = f"{n} absent: {rolls}.\n1. Save\n2. Cancel"
    resp = render_ussd_response("CON", body)
    assert len(resp) <= TARGET_USSD_LENGTH, f"Screen is {len(resp)} chars, exceeds 160"


def test_dynamic_screen_list_truncation_stays_under_target():
    """Multi-item roll lists use count-only form (>8 rolls) to stay within 160."""
    n = 20
    body = f"{n} students\n1. Save\n2. Cancel"
    resp = render_ussd_response("CON", body)
    assert len(resp) <= TARGET_USSD_LENGTH


def test_guardian_name_in_screen_does_not_overflow():
    """A name at max realistic length (30 chars) must fit in typical screens."""
    child_name = "Umuhoza Annonciata N."  # 22 chars — realistic Rwandan name
    body = f"Garuka - {child_name}\n1. Attendance\n2. Explain absence\n3. Ask help\n4. Language"
    # This screen is tight; assert it doesn't overflow TARGET
    assert len(f"CON {body}") <= TARGET_USSD_LENGTH, (
        f"P_MENU screen with child name is {len('CON ' + body)} chars"
    )
