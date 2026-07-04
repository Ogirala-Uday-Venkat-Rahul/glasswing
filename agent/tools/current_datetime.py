"""Tells the agent what today's date is.

The model's training data has a cutoff, so on its own it does not know the real
current date. That makes it fumble anything relative: "this year's model", "the
latest price", "who won last season". This tool hands it the real date so it can
turn those vague words into a concrete year before it searches.

Pure Python, no network, no arguments. About as simple as a tool gets.
"""

from datetime import datetime


def current_datetime() -> str:
    # Local time, because "today" means the day where the app is running, which
    # is what a user means when they say "this year" or "the latest".
    now = datetime.now()
    # e.g. "Friday, 03 July 2026, 14:30" -- spelled-out and unambiguous so the
    # model can't misread it (unlike 03/07 vs 07/03).
    return now.strftime("%A, %d %B %Y, %H:%M")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "current_datetime",
        "description": (
            "Get the current date and time. Use this before searching whenever "
            "the question involves relative time such as 'this year', 'latest', "
            "'current', or 'now', so you can search for the specific year."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}
