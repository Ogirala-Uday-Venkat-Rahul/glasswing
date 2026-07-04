"""The model client, and the seam for swapping providers.

Everything the agent knows about the LLM provider lives here. The rest of the
core calls chat() and never imports groq directly. To move off Groq you edit
this one file.
"""

import os
import groq
from groq import Groq


class LLMError(Exception):
    """A model call failed (rate limit, network, provider outage, ...).

    The loop catches this to degrade gracefully instead of crashing. Wrapping
    Groq's own exceptions here keeps the provider seam intact: the rest of the
    agent catches LLMError and never has to import or know about groq.
    """

# Model choice in one place. Each tier carries its model id plus any extra
# params that model needs. They live per-model because not every model accepts
# the same options: Qwen is a reasoning model and takes reasoning_effort, but
# Llama rejects that param outright, so it cannot be set globally.
#   primary  = Qwen: reasoning, vision, and tools. reasoning_effort="none" makes
#              it answer directly instead of spending its whole output budget on
#              hidden thinking (which left the final answer empty on long inputs).
#   fallback = Llama: text only, kept for later reliability work. A vision
#              request cannot fall back to a text model, a limit we call out.
MODELS = {
    "primary": {
        "model": "qwen/qwen3.6-27b",
        "params": {"reasoning_effort": "none"},
    },
    "fallback": {
        "model": "llama-3.3-70b-versatile",
        "params": {},
    },
}

# Built lazily so importing this module does not require the key to be set
# (tests monkeypatch chat() and never touch the real client).
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


def chat(messages, tools=None, tier="primary", temperature=0):
    """Send one turn to the model and return the assistant message.

    messages     the running conversation (system, user, assistant, tool)
    tools        the JSON tool schemas, or None for a plain call
    tier         "primary" or "fallback" (keys of MODELS)
    temperature  0 by default so routing and tool choice are reproducible
    """
    config = MODELS[tier]
    kwargs = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
        **config["params"],
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
        # Let the model fire independent tool calls in a single turn instead of
        # one per round-trip. It decides when to batch (we saw it group two
        # calculations but serialise two web searches, wanting the first result
        # before choosing the second query), so this is a free win when it
        # happens rather than something we force. The loop already runs every
        # call in a returned batch, so no other change is needed. Defaults true,
        # set explicitly so the intent is on the record.
        kwargs["parallel_tool_calls"] = True

    try:
        response = _get_client().chat.completions.create(**kwargs)
    except groq.APIError as exc:
        # Covers rate limits, bad-status responses, and connection failures
        # (all subclass groq.APIError). Re-raise as our own type so callers
        # depend on agent.llm, not on groq.
        raise LLMError(str(exc)) from exc
    return response.choices[0].message
