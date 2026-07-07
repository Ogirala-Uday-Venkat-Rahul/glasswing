"""Tests for the vision path (build step 5).

Two pieces, both checkable with no real R2 credentials and no live model: the
storage seam is decided purely by configuration, and building the multimodal user
message is a pure function.
"""

import agent.loop as loop
from backend import storage

_R2_KEYS = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")


def test_storage_disabled_without_credentials(monkeypatch):
    for key in _R2_KEYS:
        monkeypatch.delenv(key, raising=False)
    assert storage.is_enabled() is False


def test_storage_enabled_only_when_all_credentials_present(monkeypatch):
    for key in _R2_KEYS:
        monkeypatch.setenv(key, "x")
    assert storage.is_enabled() is True
    # Missing any single one turns it back off.
    monkeypatch.delenv("R2_BUCKET")
    assert storage.is_enabled() is False


def test_only_supported_image_types_allowed():
    assert storage.is_allowed_type("image/png")
    assert storage.is_allowed_type("image/jpeg")
    assert not storage.is_allowed_type("image/svg+xml")
    assert not storage.is_allowed_type("application/pdf")


def test_user_content_is_plain_text_without_images():
    # No images -> the content stays a plain string, exactly the pre-vision shape.
    assert loop._user_content("hello", None) == "hello"
    assert loop._user_content("hello", []) == "hello"


def test_user_content_is_multimodal_with_images():
    content = loop._user_content("what is this?", ["https://r2/one", "https://r2/two"])
    assert content == [
        {"type": "text", "text": "what is this?"},
        {"type": "image_url", "image_url": {"url": "https://r2/one"}},
        {"type": "image_url", "image_url": {"url": "https://r2/two"}},
    ]
