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

    monkeypatch.setattr(fu, "_is_safe_url", lambda url: True)
    monkeypatch.setattr(fu, "_fetch_static", lambda url: "static content")
    monkeypatch.setattr(fu, "_fetch_firecrawl", firecrawl)

    assert fu.fetch_url("http://x") == "static content"
    assert called["firecrawl"] is False


def test_falls_back_to_firecrawl(monkeypatch):
    # Static came back empty/blocked, so we fall back.
    monkeypatch.setattr(fu, "_is_safe_url", lambda url: True)
    monkeypatch.setattr(fu, "_fetch_static", lambda url: None)
    monkeypatch.setattr(fu, "_fetch_firecrawl", lambda url: "firecrawl content")

    assert fu.fetch_url("http://x") == "firecrawl content"


def test_message_when_both_fail(monkeypatch):
    monkeypatch.setattr(fu, "_is_safe_url", lambda url: True)
    monkeypatch.setattr(fu, "_fetch_static", lambda url: None)
    monkeypatch.setattr(fu, "_fetch_firecrawl", lambda url: None)

    assert "could not" in fu.fetch_url("http://x").lower()


# --- SSRF guard --------------------------------------------------------------

def test_non_http_schemes_are_refused():
    # file:// and friends must never be fetched, even if they'd "work".
    for bad in ("file:///etc/passwd", "ftp://host/x", "gopher://host", "not-a-url"):
        assert fu._is_safe_url(bad) is False


def test_private_and_metadata_hosts_are_refused(monkeypatch):
    # Resolve every host to an internal address; the guard must reject each.
    def fake_getaddrinfo(host, *args, **kwargs):
        mapping = {
            "metadata.google.internal": "169.254.169.254",  # cloud metadata
            "localhost": "127.0.0.1",
            "internal.box": "10.1.2.3",
            "router": "192.168.0.1",
        }
        return [(2, 1, 6, "", (mapping[host], 0))]

    monkeypatch.setattr(fu.socket, "getaddrinfo", fake_getaddrinfo)
    for host in ("metadata.google.internal", "localhost", "internal.box", "router"):
        assert fu._is_safe_url(f"http://{host}/") is False


def test_public_host_is_allowed(monkeypatch):
    monkeypatch.setattr(
        fu.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))]
    )
    assert fu._is_safe_url("https://example.com/page") is True


def test_unsafe_url_short_circuits_before_any_fetch(monkeypatch):
    # An unsafe URL must never reach the fetchers at all.
    monkeypatch.setattr(fu, "_is_safe_url", lambda url: False)
    monkeypatch.setattr(
        fu, "_fetch_static", lambda url: (_ for _ in ()).throw(AssertionError("fetched"))
    )
    assert "can't be fetched" in fu.fetch_url("http://169.254.169.254/").lower()


def test_redirect_to_internal_host_is_blocked(monkeypatch):
    # A public URL that 302s to the metadata IP must be dropped at the hop.
    monkeypatch.setattr(fu, "_is_safe_url", lambda url: "example.com" in url)

    class FakeResp:
        is_redirect = True
        headers = {"location": "http://169.254.169.254/latest/meta-data/"}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            return FakeResp()

    monkeypatch.setattr(fu.httpx, "Client", lambda **k: FakeClient())
    assert fu._fetch_static("https://example.com/start") is None


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
    monkeypatch.setattr(fu, "_is_safe_url", lambda url: True)
    monkeypatch.setattr(fu, "_fetch_static", lambda url: noise + "The answer is 42.")

    assert "The answer is 42." in fu.fetch_url("http://x")
