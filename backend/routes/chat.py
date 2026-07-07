"""The streaming /chat endpoint (build steps 2 and 3).

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

Build step 3 adds persistence around the run: we load the conversation's prior
turns to give the agent memory, save the new user message, and save the final
answer. All of that also happens on the worker thread (blocking DB I/O belongs
off the event loop), and it degrades to a stateless run if no database is set.
"""

import asyncio
import json
import uuid

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent.loop import run
from agent.tools.remember import make_remember_tool

from .. import auth, storage, store
from ..db import new_session

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    # Omitted on the first turn -> the server mints a new conversation id and
    # returns it. Sent back on later turns to continue the same conversation.
    conversation_id: str | None = None
    # The R2 object key returned by /upload, when the user attached an image to
    # this turn. We presign it into a URL the vision model can fetch, and store the
    # key as a pointer on the message.
    image_key: str | None = None


# A unique object that means "the agent run is over". We put it on the queue
# when the worker finishes so the async generator knows to stop awaiting.
_DONE = object()


@router.post("/chat")
async def chat(request: ChatRequest, http_request: Request):
    # The event loop and queue live on this request's async task. The worker
    # thread will reach back into this loop to deliver each step.
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    is_new = request.conversation_id is None
    conversation_id = request.conversation_id or uuid.uuid4().hex

    # Who's asking? Read the same signed session cookie the auth routes set. None
    # if signed out -- the chat still works, the conversation is just left unowned
    # (same graceful degrade as running with no database at all).
    user_id = auth.read_session(http_request.cookies.get(auth.SESSION_COOKIE))

    def on_step(step) -> None:
        # Runs in the worker thread. asyncio.Queue is not thread-safe, so we do
        # not call put_nowait directly; call_soon_threadsafe schedules it on the
        # event loop thread, which is the only place it is safe to touch.
        loop.call_soon_threadsafe(queue.put_nowait, step.to_dict())

    def work() -> None:
        # The blocking agent run plus its history reads/writes, on their own
        # thread. run() already catches tool and model failures and emits them as
        # error steps; we guard here too so any unexpected crash still surfaces as
        # an event instead of a silent dead stream, and the finally always
        # releases the generator.
        db = new_session()  # None if DATABASE_URL is not configured

        history = []
        memories = None
        remember_tool = None
        if db is not None:
            # Persistence failures must not fail the chat: fall back to a
            # stateless run rather than 500 if the database is momentarily down.
            try:
                if is_new:
                    store.create_conversation(
                        db, conversation_id, user_id=user_id, title=request.message[:60]
                    )
                history = store.load_history(db, conversation_id)
                store.add_message(
                    db, conversation_id, "user", request.message, image_key=request.image_key
                )
                db.commit()
            except Exception as exc:  # noqa: BLE001 - degrade, don't crash
                db.rollback()
                print(f"[chat] history load/save failed, continuing stateless: {exc}")

            # Long-term memory is per-user, so it only applies when signed in.
            # Load what we already know (recall) and bind a save tool to this
            # user + session (capture) for the agent to call mid-run.
            if user_id is not None:
                try:
                    memories = store.list_memories(db, user_id)
                    remember_tool = make_remember_tool(
                        lambda fact: store.add_memory(db, user_id, fact)
                    )
                except Exception as exc:  # noqa: BLE001 - memory is a bonus, not required
                    print(f"[chat] memory load failed, continuing without it: {exc}")

        # If the user attached an image, presign its R2 key into a URL the vision
        # model can fetch for this turn. Done outside the db block because images
        # work with or without persistence; skipped cleanly if R2 isn't configured.
        images = None
        if request.image_key and storage.is_enabled():
            try:
                images = [storage.view_url(request.image_key)]
            except Exception as exc:  # noqa: BLE001 - a bad key shouldn't sink the chat
                print(f"[chat] could not presign image, continuing without it: {exc}")

        try:
            answer = run(
                request.message,
                on_step=on_step,
                history=history,
                memories=memories,
                remember=remember_tool,
                images=images,
            )
            if db is not None:
                try:
                    store.add_message(db, conversation_id, "assistant", answer)
                    db.commit()
                except Exception as exc:  # noqa: BLE001 - answer already streamed
                    db.rollback()
                    print(f"[chat] answer save failed: {exc}")
        except Exception as exc:  # last-resort guard for the stream
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "error", "content": f"Unexpected server error: {exc}"},
            )
        finally:
            if db is not None:
                db.close()
            loop.call_soon_threadsafe(queue.put_nowait, _DONE)

    async def event_stream():
        # First frame tells the client which conversation this is, so it can send
        # the id back on the next turn to continue the thread.
        yield {"event": "meta", "data": json.dumps({"conversation_id": conversation_id})}

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
