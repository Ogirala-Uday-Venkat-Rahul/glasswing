"""Top headlines via Serper's Google News endpoint (opt-in news panel).

Optional, like every other seam in the app: with no SERPER_API_KEY the endpoint
returns an empty list instead of erroring, so the feature degrades cleanly and
the frontend simply shows nothing. The panel is opt-in on the client, so this is
only ever hit when the user asks for it. Each headline it returns becomes a
one-click prompt into the same agent loop -- news and chat share one path.
"""

import os

import httpx
from fastapi import APIRouter

router = APIRouter()

SERPER_NEWS_URL = "https://google.serper.dev/news"

# A handful of headlines: enough to scan at a glance, few enough to keep the
# sidebar panel calm and the Serper response (and its token cost, when a headline
# is clicked into the agent) small.
MAX_HEADLINES = 6


def _headlines(data: dict) -> list[dict]:
    """Pull the fields the panel needs out of a Serper news response.

    Pure (no network), so the route stays a thin shell around it and this is easy
    to test -- the same split web_search uses for its _format helper. Items with
    no title are skipped; the rest are trimmed to just what the UI renders.
    """
    out = []
    for item in (data.get("news") or [])[:MAX_HEADLINES]:
        title = item.get("title")
        if not title:
            continue
        out.append(
            {
                "title": title,
                "source": item.get("source"),
                "date": item.get("date"),
                "link": item.get("link"),
            }
        )
    return out


@router.get("/news")
async def news(topic: str = "top stories"):
    """Return a few current headlines for the opt-in sidebar panel.

    `topic` is the Google News query, defaulting to general top stories. Any
    failure (missing key, provider down, malformed response) comes back as an
    empty list rather than an error, matching the app's degrade-don't-crash style.
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return {"headlines": []}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                SERPER_NEWS_URL,
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": topic, "num": MAX_HEADLINES},
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # noqa: BLE001 - a news hiccup must never 500 the app
        print(f"[news] fetch failed: {exc}")
        return {"headlines": []}
    return {"headlines": _headlines(data)}
