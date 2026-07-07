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
from .tools.remember import SCHEMA as REMEMBER_SCHEMA

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


def _system_content(memories, can_remember) -> str:
    """The system prompt, plus what the agent knows about this user this run.

    Remembered facts are folded into the single system message (rather than a
    second one) so every provider handles it the same way. When the remember
    tool is available we also nudge the model to use it, so saving a new fact is
    a habit and not something it only does when explicitly asked.
    """
    content = SYSTEM_PROMPT
    if memories:
        facts = "\n".join(f"- {m}" for m in memories)
        content += (
            "\n\nWhat you already know about this user, from earlier "
            f"conversations:\n{facts}\n"
            "Use these facts naturally when relevant; don't ask for what you "
            "already know."
        )
    if can_remember:
        content += (
            "\n\nWhen the user shares a durable fact about themselves (their name, "
            "preferences, ongoing projects), call the remember tool to save it for "
            "next time."
        )
    return content


def run(user_message: str, on_step=None, history=None, memories=None, remember=None) -> str:
    """Run the agent to completion and return its final answer text.

    on_step, if given, is called with each Step as it happens (this is how the
    backend will push events into the SSE stream).

    history, if given, is the prior turns of this conversation as a list of
    {"role", "content"} dicts (user and assistant messages only). It is slotted
    in between the system prompt and the new user message, which is what turns a
    stateless call into a multi-turn one. We store and replay only those durable
    turns, never the tool-call scratch a run generates, so the replayed context
    stays small. Defaulting to None keeps a plain single-shot call unchanged.

    memories / remember add per-user long-term memory, and are supplied by the
    backend (which alone knows the user). memories is a list of remembered facts
    injected into the system prompt (recall); remember is a bound tool the agent
    can call to save a new fact (capture). Both omitted -> the agent runs with no
    memory, exactly as before, so a logged-out or DB-less run is unchanged.
    """
    tracer = trace.start_trace("agent_run")

    # Only the tools for this run: the always-on set, plus remember when the
    # backend supplied a bound one. The core never hard-codes the memory tool.
    active_tools = dict(TOOLS)
    active_schemas = list(SCHEMAS)
    if remember is not None:
        active_tools["remember"] = remember
        active_schemas.append(REMEMBER_SCHEMA)

    messages = [{"role": "system", "content": _system_content(memories, remember is not None)}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    def emit(step: Step) -> None:
        tracer.event(step)
        if on_step is not None:
            on_step(step)

    def emit_token(text: str) -> None:
        # The live typewriter feed. Deliberately skips the tracer: tokens are an
        # ephemeral preview, and the committed thinking / final_answer step that
        # follows is what the trace records. Nothing to show -> nothing emitted.
        if on_step is not None:
            on_step(Step("token", content=text))

    def ask_model(tools=None):
        """Call the model, degrading gracefully if the provider errors.

        Returns the assistant message, or None if the call failed. On failure
        we emit an error step and end the trace, so the caller only has to bail
        out with a friendly message. This is the model-call twin of the tool
        error handling below: neither a bad tool nor a flaky provider should
        ever crash the run with a raw traceback.
        """
        try:
            return llm.chat(_for_model(messages), tools=tools, on_token=emit_token)
        except llm.LLMError as exc:
            emit(Step("error", content=f"The model call failed: {exc}"))
            tracer.end()
            return None

    for _ in range(MAX_STEPS):
        message = ask_model(tools=active_schemas)
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

            tool = active_tools.get(name)
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
