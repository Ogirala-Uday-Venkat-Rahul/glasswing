"""Plain data types shared across the agent core.

These are deliberately framework-free (no FastAPI, no pydantic). The agent core
knows nothing about HTTP. The backend layer will adapt these into SSE events.
Keeping that boundary clean means the loop can be unit tested with no server.
"""

from dataclasses import dataclass, asdict, field
from typing import Optional


# The things that can happen in the timeline the user watches.
#   token         one streamed chunk of the model's live output (typewriter feed)
#   thinking      the model's reasoning text before it acts (the committed block)
#   tool_call     the model asked to run a tool, with its arguments
#   tool_result   what the tool returned
#   final_answer  the model is done and answered
#   error         something went wrong (bad tool call, step limit, etc.)
#
# token is the live preview: chunks stream in as the model generates, and the
# UI shows them typing. Whatever the output turns out to be -- reasoning before a
# tool call, or the final answer -- a committed step (thinking / final_answer)
# follows and supersedes the preview, so tokens never need to be stored.
STEP_TYPES = ("token", "thinking", "tool_call", "tool_result", "final_answer", "error")


@dataclass
class Step:
    """One event in the agent's run. This is what streams to the UI."""

    type: str
    content: str = ""
    tool: Optional[str] = None
    args: Optional[dict] = None

    def to_dict(self) -> dict:
        # Drop empty fields so an SSE payload stays small and clean.
        return {k: v for k, v in asdict(self).items() if v not in (None, "")}
