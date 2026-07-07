"""The `remember` tool: the agent's long-term, per-user memory.

Unlike the other tools, this one can't be a plain module-level function -- saving
a fact needs to know *which user* is talking and needs a database handle, and the
agent core deliberately knows about neither. So we ship the SCHEMA here (it's just
data) plus a factory: the backend, which does have the user and the database,
calls make_remember_tool(save) to bind a persistence function into a ready tool,
then hands that tool to run() for the request. The agent core stays generic; the
user-scoped part lives where the user context already is.

The recall half (loading saved facts back into the prompt) happens in the loop
via run(memories=...); this file is only the write path.
"""

SCHEMA = {
    "type": "function",
    "function": {
        "name": "remember",
        "description": (
            "Save a durable fact about the user so you still know it in future "
            "conversations -- their name, preferences, ongoing projects, or "
            "anything they'd expect you to recall later. Call this the moment the "
            "user shares such a fact. Do NOT use it for one-off or trivial details, "
            "and don't save something you were already told (it's shown to you)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": (
                        "The fact as a short, self-contained statement, e.g. "
                        "'Name is Naruto' or 'Prefers Python over JavaScript'."
                    ),
                }
            },
            "required": ["fact"],
        },
    },
}


def make_remember_tool(save):
    """Wrap a persistence callable into the remember(fact) tool the loop runs.

    `save(fact: str)` does the actual storing (the backend supplies one bound to
    the current user + session). We add the input guard and the friendly return
    string here so that contract lives with the tool, not scattered per caller.
    """

    def remember(fact: str = "") -> str:
        fact = (fact or "").strip()
        if not fact:
            return "Nothing to remember."
        save(fact)
        return f"Noted — I'll remember that: {fact}"

    return remember
