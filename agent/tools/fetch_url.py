"""Fetch a web page and extract its readable text, with a Firecrawl fallback.

Two paths, tried in order:

  1. Static: httpx GET + trafilatura. Free and fast, and enough for most pages.
  2. Firecrawl: a headless browser that runs JavaScript and handles many
     bot-protected pages. Used only when the static path comes back empty or
     blocked (for example a 403), and only if FIRECRAWL_API_KEY is set. Same
     seam idea as trace.py: no key means the fallback is simply off.

trafilatura is used rather than hand-rolled HTML parsing because turning messy
HTML into clean article text is a genuinely hard problem and a library is the
right call.
"""

import os
import re

import httpx
import trafilatura

# Markdown a text model cannot use, and that inflates every fetched page. Images
# carry only long URLs (no visual value to the model); links wrap useful anchor
# text around URLs the model does not need to see inline. Stripping these is what
# makes truncation keep signal instead of a screen of image URLs.
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")          # ![alt](url)  -> drop
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")          # [text](url)  -> text
_BLANK_RUN = re.compile(r"\n[ \t]*\n[ \t]*(?:\n[ \t]*)+")  # 3+ newlines -> one gap


def _clean(text: str) -> str:
    """Strip markdown noise and collapse whitespace so the kept text is signal.

    Applied to both extraction paths, so no matter which fetcher ran, the model
    receives compact readable text rather than a wall of image and link URLs.
    """
    text = _MD_IMAGE.sub("", text)
    text = _MD_LINK.sub(r"\1", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip()

# Keep returned text bounded so one page cannot blow up the model context.
# Kept deliberately tight: on Groq's free tier the whole request must fit in
# 8000 tokens/minute, and one full page (~2500 tokens at 8000 chars) plus the
# running conversation is enough to blow that budget. 3000 chars (~900 tokens)
# still captures the part of the page that answers most questions.
MAX_CHARS = 3000

FIRECRAWL_URL = "https://api.firecrawl.dev/v2/scrape"


def fetch_url(url: str) -> str:
    # Free, fast path first.
    text = _fetch_static(url)
    if text:
        return _clean(text)[:MAX_CHARS]

    # Static got nothing (JavaScript-heavy page) or was blocked. Try Firecrawl
    # if it is configured.
    text = _fetch_firecrawl(url)
    if text:
        return _clean(text)[:MAX_CHARS]

    return "Could not fetch readable content from that page."


def _fetch_static(url: str) -> str | None:
    try:
        response = httpx.get(
            url,
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Glasswing/1.0"},
        )
        response.raise_for_status()
    except httpx.HTTPError:
        # Blocked, timed out, or errored. Return None so the fallback can try.
        return None
    return trafilatura.extract(response.text)


def _fetch_firecrawl(url: str) -> str | None:
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        # Fallback not configured. Stay on the free path only.
        return None
    try:
        response = httpx.post(
            FIRECRAWL_URL,
            timeout=30,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    return response.json().get("data", {}).get("markdown")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": (
            "Fetch a web page by URL and return its main readable text. "
            "Use this to read a page found via web_search."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full URL to fetch"}
            },
            "required": ["url"],
        },
    },
}
