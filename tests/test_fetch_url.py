"""Test the static -> Firecrawl fallback decision without hitting the network.

We monkeypatch the two internal fetchers so the test is deterministic and offline.
"""

import importlib

# The tools package re-exports the fetch_url *function* under the name
# "fetch_url", which shadows the submodule on attribute access. Import the
# module explicitly so we can monkeypatch its internal helpers.
fu = importlib.import_module("agent.tools.fetch_url")


def test_uses_static_when_it_works(monkeypatch):
    # Static path returns text, so Firecrawl must never be called.
    called = {"firecrawl": False}

    def firecrawl(url):
        called["firecrawl"] = True
        return "should not be used"

    monkeypatch.setattr(fu, "_fetch_static", lambda url: "static content")
    monkeypatch.setattr(fu, "_fetch_firecrawl", firecrawl)

    assert fu.fetch_url("http://x") == "static content"
    assert called["firecrawl"] is False


def test_falls_back_to_firecrawl(monkeypatch):
    # Static came back empty/blocked, so we fall back.
    monkeypatch.setattr(fu, "_fetch_static", lambda url: None)
    monkeypatch.setattr(fu, "_fetch_firecrawl", lambda url: "firecrawl content")

    assert fu.fetch_url("http://x") == "firecrawl content"


def test_message_when_both_fail(monkeypatch):
    monkeypatch.setattr(fu, "_fetch_static", lambda url: None)
    monkeypatch.setattr(fu, "_fetch_firecrawl", lambda url: None)

    assert "could not" in fu.fetch_url("http://x").lower()


def test_clean_strips_markdown_noise():
    # Images drop entirely; links keep only their visible text; runs of blank
    # lines collapse. The price-like signal survives, the URL bloat does not.
    raw = (
        "# Product\n"
        "![product image](https://cdn.example.com/very/long/image/url.jpg)\n\n\n\n"
        "Price: $799.00\n"
        "[Shop now](https://www.example.com/deals?ref=abc123)\n"
    )
    cleaned = fu._clean(raw)

    assert "$799.00" in cleaned
    assert "Shop now" in cleaned          # anchor text kept
    assert "http" not in cleaned          # every URL gone
    assert "\n\n\n" not in cleaned        # blank-line runs collapsed


def test_clean_applied_before_truncation(monkeypatch):
    # A page that is mostly image-URL noise followed by the real content: after
    # cleaning, the content survives truncation instead of being pushed past it.
    noise = "![x](https://cdn.example.com/" + "a" * 5000 + ".jpg)\n"
    monkeypatch.setattr(fu, "_fetch_static", lambda url: noise + "The answer is 42.")

    assert "The answer is 42." in fu.fetch_url("http://x")
