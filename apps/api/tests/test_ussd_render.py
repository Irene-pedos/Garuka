import pytest

from app.services.ussd.render import MAX_USSD_LENGTH, USSDLengthExceededError, render_ussd_response


def test_render_con_response():
    resp = render_ussd_response("CON", "Welcome to Garuka")
    assert resp == "CON Welcome to Garuka"
    assert len(resp) <= MAX_USSD_LENGTH


def test_render_end_response():
    resp = render_ussd_response("END", "Session completed")
    assert resp == "END Session completed"
    assert len(resp) <= MAX_USSD_LENGTH


def test_render_invalid_kind():
    with pytest.raises(ValueError, match="Invalid USSD response kind"):
        render_ussd_response("UNKNOWN", "Test")


def test_render_exceeding_hard_limit():
    long_body = "x" * 180  # "CON " (4 chars) + 180 = 184 > 182
    with pytest.raises(USSDLengthExceededError, match="exceeds hard limit"):
        render_ussd_response("CON", long_body)


def test_render_exact_hard_limit():
    exact_body = "x" * 178  # "CON " (4 chars) + 178 = 182
    resp = render_ussd_response("CON", exact_body)
    assert len(resp) == 182
