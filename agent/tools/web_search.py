"""Web search via Serper (Google Search results).

Serper returns real Google results, so the agent finds what a person would find
searching Google, including the answer box and the knowledge panel (the entity
card with type, description, and details like an address). Tavily, the earlier
choice, is optimized to feed an LLM raw text and does not match Google's ranking
or expose a knowledge graph. Because this whole tool sits behind one file, the
switch was a one-file change: the loop and schema are untouched.
"""

import os

import httpx

# Three results, not five. The answer box and knowledge panel usually carry the
# fact; among the blue links the top three are the ones the model actually uses,
# while 4 and 5 mostly add tokens we re-send on every later step. Trimming here is
# the cleanest search-side token saving that does not touch what the model can do
# (it keeps every URL, so fetch_url still works).
MAX_RESULTS = 3
# Cap each result's summary so one long page cannot flood the model's context or
# the step timeline. Serper's snippets run ~150 chars, so 200 keeps them whole
# while bounding the outliers. The model can fetch_url to read a page in full.
SNIPPET_CHARS = 200

SERPER_URL = "https://google.serper.dev/search"


def web_search(query: str) -> str:
    response = httpx.post(
        SERPER_URL,
        timeout=20,
        headers={
            "X-API-KEY": os.environ["SERPER_API_KEY"],
            "Content-Type": "application/json",
        },
        json={"q": query, "num": MAX_RESULTS},
    )
    response.raise_for_status()
    return _format(response.json())


def _format(data: dict) -> str:
    """Turn a Serper response into readable text. Pure, so it is easy to test."""
    parts = []

    # Google's instant answer, when there is one.
    answer_box = data.get("answerBox")
    if answer_box:
        answer = answer_box.get("answer") or answer_box.get("snippet")
        if answer:
            parts.append(f"Answer: {answer}")

    # The knowledge panel: the entity card a person sees on the right of Google.
    knowledge = data.get("knowledgeGraph")
    if knowledge:
        lines = [f"Knowledge panel: {knowledge.get('title', '')}"]
        if knowledge.get("type"):
            lines.append(f"  Type: {knowledge['type']}")
        if knowledge.get("description"):
            lines.append(f"  {knowledge['description']}")
        for key, value in (knowledge.get("attributes") or {}).items():
            lines.append(f"  {key}: {value}")
        parts.append("\n".join(lines))

    # The organic (blue-link) results.
    organic = data.get("organic", [])
    if organic:
        lines = []
        for result in organic[:MAX_RESULTS]:
            snippet = (result.get("snippet") or "")[:SNIPPET_CHARS]
            lines.append(
                f"- {result.get('title', '')}\n  {result.get('link', '')}\n  {snippet}"
            )
        parts.append("\n".join(lines))

    if not parts:
        return "No results found."
    return "\n\n".join(parts)


SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search Google for current information. Returns the answer box and "
            "knowledge panel when present, plus titles, URLs, and short summaries. "
            "Use fetch_url to read any result in full."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"],
        },
    },
}
