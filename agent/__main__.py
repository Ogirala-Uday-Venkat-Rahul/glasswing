"""Run the agent from the command line and watch the timeline print.

    python -m agent "What is 4823 * 197?"

Reads keys from .env. This is the step-1 test harness: no server, no auth.
"""

import sys

from dotenv import load_dotenv

from .loop import run
from .schemas import Step


def print_step(step: Step) -> None:
    if step.type == "tool_call":
        print(f"  [tool_call] {step.tool}({step.args})")
    elif step.type == "tool_result":
        print(f"  [tool_result] {step.tool} -> {step.content}")
    elif step.type == "thinking":
        print(f"  [thinking] {step.content}")
    elif step.type == "final_answer":
        print(f"\n[answer] {step.content}")
    elif step.type == "error":
        print(f"\n[error] {step.content}")


def main() -> None:
    load_dotenv()
    if len(sys.argv) < 2:
        print('Usage: python -m agent "your question"')
        raise SystemExit(1)
    run(sys.argv[1], on_step=print_step)


if __name__ == "__main__":
    main()
