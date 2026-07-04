"""Plain data types shared across the agent core.

These are deliberately framework-free (no FastAPI, no pydantic). The agent core
knows nothing about HTTP. The backend layer will adapt these into SSE events.
Keeping that boundary clean means the loop can be unit tested with no server.
"""

from dataclasses import dataclass, asdict, field
from typing import Optional


# The five things that can happen in the timeline the user watches.
#   thinking      the model's reasoning text before it acts
#   tool_call     the model asked to run a tool, with its arguments
#   tool_result   what the tool returned
#   final_answer  the model is done and answered
#   error         something went wrong (bad tool call, step limit, etc.)
STEP_TYPES = ("thinking", "tool_call", "tool_result", "final_answer", "error")


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
