"""The hand-rolled tool-calling loop.

This is the whole agent. In plain words:

  1. Send the conversation to the model, along with the tool schemas.
  2. If the model asked for tools, run each one and feed the results back.
  3. Repeat until the model answers normally, or we hit a step cap.

Every step is reported through on_step so the UI can show the timeline live,
and through the tracer so it can be recorded.
"""

import json

from . import grounding, llm, trace
from .schemas import Step
from .tools import TOOLS, SCHEMAS

# Hard stop so a confused model can never loop forever (each pass is a paid
# model call). If we hit this, we report an error rather than hang.
MAX_STEPS = 8

# Kept deliberately short: the tools already describe themselves in their schemas
# (sent every call), so this holds only the behaviour those descriptions cannot —
# how to search, which sources to trust, and how to answer. Each line here earns
# its tokens because it is re-sent on every model call.
SYSTEM_PROMPT = (
    "You are Glasswing, a helpful assistant that answers using your tools. "
    "Search a company or product by its plain name (e.g. 'sstech', not 'sstech "
    "website') to surface Google's knowledge panel. "
    "Trust authoritative sources — official sites, manufacturers, major retailers "
    "like Amazon or Best Buy — over forums, Reddit, or YouTube. "
    "State a specific figure such as a price only if it appears in your tool "
    "results; never supply one from memory. "
    "Don't over-search: once a reliable source gives the key facts, stop; if "
    "something stays uncertain, say so plainly. "
    "Answer concisely in your own words — never paste raw results — and focus on "
    "the entity the user asked about."
)


def _evidence(messages) -> str:
    """Concatenate everything the tools returned this run.

    This is the ground truth the grounding check verifies the answer against:
    the search snippets and fetched pages are still sitting in the conversation
    as tool messages, so we never have to re-fetch or ask another model.
    """
    return "\n".join(
        m["content"] for m in messages if m.get("role") == "tool" and m.get("content")
    )


# How many of the most recent tool results the model still sees in full. The
# model acts on an observation the moment it arrives; on later steps it needs its
# own reasoning trail more than the raw text again. Keeping the last two whole
# covers the common single- and double-search queries untouched, and only starts
# trimming on longer chains -- exactly where the re-sent tokens pile up.
KEEP_RECENT_OBSERVATIONS = 2


def _for_model(messages):
    """A copy of the conversation with old tool results compacted for sending.

    The loop re-sends the whole conversation on every call, and raw observations
    are the fat part of it. We replace all but the most recent few tool results
    with a short stub, which keeps the message structure (and the tool_call_id
    pairing the API requires) intact while cutting the tokens we re-send. The
    real messages list is never touched, so grounding and the timeline still see
    every result in full.
    """
    tool_positions = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    keep = set(tool_positions[-KEEP_RECENT_OBSERVATIONS:])
    trimmed = []
    for i, m in enumerate(messages):
        if m.get("role") == "tool" and i not in keep:
            trimmed.append({**m, "content": "[earlier tool result omitted to save context]"})
        else:
            trimmed.append(m)
    return trimmed


def run(user_message: str, on_step=None) -> str:
    """Run the agent to completion and return its final answer text.

    on_step, if given, is called with each Step as it happens (this is how the
    backend will push events into the SSE stream).
    """
    tracer = trace.start_trace("agent_run")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    def emit(step: Step) -> None:
        tracer.event(step)
        if on_step is not None:
            on_step(step)

    def ask_model(tools=None):
        """Call the model, degrading gracefully if the provider errors.

        Returns the assistant message, or None if the call failed. On failure
        we emit an error step and end the trace, so the caller only has to bail
        out with a friendly message. This is the model-call twin of the tool
        error handling below: neither a bad tool nor a flaky provider should
        ever crash the run with a raw traceback.
        """
        try:
            return llm.chat(_for_model(messages), tools=tools)
        except llm.LLMError as exc:
            emit(Step("error", content=f"The model call failed: {exc}"))
            tracer.end()
            return None

    for _ in range(MAX_STEPS):
        message = ask_model(tools=SCHEMAS)
        if message is None:
            return "Sorry — I couldn't reach the model just now. Please try again."

        # No tool calls means the model is done and this is the answer.
        if not message.tool_calls:
            answer = message.content or ""
            answer = grounding.ground_answer(answer, _evidence(messages), asked=user_message)
            emit(Step("final_answer", content=answer))
            tracer.end()
            return answer

        # The model wants tools. We must append its message (with the tool_calls)
        # before the tool results, or the API rejects the next request: every
        # tool result has to answer a tool_call the model can see.
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
        )

        if message.content:
            emit(Step("thinking", content=message.content))

        for tc in message.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            emit(Step("tool_call", tool=name, args=args))

            tool = TOOLS.get(name)
            if tool is None:
                result = f"Unknown tool: {name}"
            else:
                # A tool failure is fed back to the model as the result, not
                # raised. That lets the model recover (retry, try another tool,
                # or explain) instead of crashing the whole run.
                try:
                    result = str(tool(**args))
                except Exception as exc:
                    result = f"Tool error: {exc}"

            emit(Step("tool_result", tool=name, content=result))
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": result}
            )

    # We hit the step cap without the model choosing to answer. Rather than abort
    # with a cold error, make one last call with NO tools available. Offering no
    # tools forces the model to answer from what it has already gathered, so the
    # user gets a useful (if hedged) reply instead of a dead end. This is the
    # loop's graceful degradation: knowing when to stop is part of the design.
    messages.append(
        {
            "role": "user",
            "content": (
                "You are out of tool calls. Answer now using only what you have "
                "gathered so far. If a detail is uncertain or missing, say so "
                "plainly rather than guessing."
            ),
        }
    )
    message = ask_model()  # no tools -> the model has to answer directly
    if message is None:
        return "Sorry — I couldn't reach the model just now. Please try again."
    answer = message.content or "I couldn't find enough to answer that."
    answer = grounding.ground_answer(answer, _evidence(messages), asked=user_message)
    emit(Step("final_answer", content=answer))
    tracer.end()
    return answer
