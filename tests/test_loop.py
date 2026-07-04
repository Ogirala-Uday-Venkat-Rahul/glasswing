"""Test the loop's control flow without touching the network.

We monkeypatch llm.chat to return a scripted sequence of model responses, so the
test is deterministic: first the model asks for the calculator, then it answers.
This proves the loop runs the tool, feeds the result back, and terminates.
"""

from types import SimpleNamespace

from agent import loop
from agent.schemas import Step


def _tool_call(name, arguments, call_id="call_1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _message(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def test_loop_runs_tool_then_answers(monkeypatch):
    # Turn 1: model wants the calculator. Turn 2: model gives a final answer.
    responses = iter(
        [
            _message(tool_calls=[_tool_call("calculator", '{"expression": "2 + 2"}')]),
            _message(content="The answer is 4.", tool_calls=None),
        ]
    )
    monkeypatch.setattr(loop.llm, "chat", lambda *a, **k: next(responses))

    steps = []
    answer = loop.run("what is 2 + 2?", on_step=steps.append)

    assert answer == "The answer is 4."

    # The calculator actually ran and returned 4, fed back as a tool_result.
    results = [s for s in steps if s.type == "tool_result"]
    assert results and results[0].tool == "calculator"
    assert results[0].content == "4"


def test_prune_stubs_old_observations_but_keeps_recent():
    # Three tool results; only the most recent KEEP_RECENT_OBSERVATIONS stay whole.
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "q"},
        {"role": "tool", "tool_call_id": "a", "content": "OLD price $100"},
        {"role": "tool", "tool_call_id": "b", "content": "MID price $200"},
        {"role": "tool", "tool_call_id": "c", "content": "NEW price $300"},
    ]

    sent = loop._for_model(messages)

    # The oldest observation is stubbed; the two most recent survive in full.
    assert "OLD price $100" not in sent[2]["content"]
    assert "omitted" in sent[2]["content"]
    assert sent[3]["content"] == "MID price $200"
    assert sent[4]["content"] == "NEW price $300"
    # The tool_call_id pairing the API requires is preserved on the stub.
    assert sent[2]["tool_call_id"] == "a"
    # The real conversation is untouched, so grounding still sees every result.
    assert "OLD price $100" in loop._evidence(messages)


def test_loop_degrades_gracefully_at_step_limit(monkeypatch):
    # A model that keeps asking for a tool must be cut off at the cap. Instead of
    # erroring out, the loop makes one final call with NO tools offered, which
    # forces a direct answer from what it already has. We detect that final call
    # by the absence of a tools= argument and return a scripted answer for it.
    def fake_chat(messages, tools=None, **kwargs):
        if tools is None:
            return _message(content="Here is my best answer with what I have.")
        return _message(
            tool_calls=[_tool_call("calculator", '{"expression": "1 + 1"}')]
        )

    monkeypatch.setattr(loop.llm, "chat", fake_chat)

    steps = []
    answer = loop.run("loop forever", on_step=steps.append)

    # The loop was cut off (it looped, running the tool) but still ended on a
    # real answer rather than an error.
    assert answer == "Here is my best answer with what I have."
    assert steps[-1].type == "final_answer"
    assert any(s.type == "tool_result" for s in steps)
