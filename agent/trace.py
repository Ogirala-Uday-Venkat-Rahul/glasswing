"""Observability seam.

The core loop calls start_trace() and then tracer.event(step) for each step.
By default this is a no-op: no Langfuse dependency, no network, nothing. Tracing
turns on only when a Langfuse key is present in the environment, so the loop
stays clean and testable and observability is optional and swappable.
"""

import os


class _NoOpTracer:
    def event(self, step):
        pass

    def end(self):
        pass


def _tracing_enabled() -> bool:
    return bool(os.environ.get("LANGFUSE_SECRET_KEY"))


def start_trace(name: str):
    if not _tracing_enabled():
        return _NoOpTracer()

    # Real Langfuse wiring lands when we turn tracing on (build step 8).
    # Kept behind this guard and a lazy import so langfuse is never required
    # unless the key is actually set.
    #   from langfuse import Langfuse
    #   ... build and return a real tracer with the same .event()/.end() shape
    return _NoOpTracer()
