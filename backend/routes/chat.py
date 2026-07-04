"""The streaming /chat endpoint (build step 2).

This is where the two worlds meet. The agent core (agent/loop.py) is a plain
synchronous function that *pushes* each Step to a callback as it happens. SSE,
on the other hand, is asynchronous and *pulls*: an async generator has to yield
events one at a time. This module bridges push -> pull without touching the
agent core at all, which is the whole point of keeping Step framework-free.

The bridge, in three moving parts:
  1. run() is blocking (it makes network calls to Groq), so we run it in a
     worker thread. If we called it directly it would freeze the event loop and
     no events could go out until the whole run finished.
  2. Its on_step callback fires inside that worker thread. It hands each Step
     back to the event loop with call_soon_threadsafe, the one safe way to touch
     an asyncio object from another thread, dropping it onto an asyncio.Queue.
  3. An async generator awaits that queue and yields each Step as an SSE event.
"""

import asyncio
import json

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent.loop import run

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


# A unique object that means "the agent run is over". We put it on the queue
# when the worker finishes so the async generator knows to stop awaiting.
_DONE = object()


@router.post("/chat")
async def chat(request: ChatRequest):
    # The event loop and queue live on this request's async task. The worker
    # thread will reach back into this loop to deliver each step.
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def on_step(step) -> None:
        # Runs in the worker thread. asyncio.Queue is not thread-safe, so we do
        # not call put_nowait directly; call_soon_threadsafe schedules it on the
        # event loop thread, which is the only place it is safe to touch.
        loop.call_soon_threadsafe(queue.put_nowait, step.to_dict())

    def work() -> None:
        # The blocking agent run, on its own thread. run() already catches tool
        # and model failures and emits them as error steps, but we guard here too
        # so any unexpected crash still surfaces as an event instead of a silent
        # dead stream. The finally guarantees the generator is always released.
        try:
            run(request.message, on_step=on_step)
        except Exception as exc:  # last-resort guard for the stream
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "error", "content": f"Unexpected server error: {exc}"},
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _DONE)

    async def event_stream():
        # Kick the blocking work onto a thread from the default executor. We do
        # not await it: it feeds the queue on its own while we drain below.
        loop.run_in_executor(None, work)
        while True:
            item = await queue.get()
            if item is _DONE:
                break
            # Named "step" events so the frontend can addEventListener("step").
            # data must be a string, so each Step dict is serialised to JSON.
            yield {"event": "step", "data": json.dumps(item)}

    return EventSourceResponse(event_stream())
