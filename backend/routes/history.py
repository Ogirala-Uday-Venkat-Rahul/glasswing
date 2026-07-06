"""Read endpoint for a stored conversation (build step 3).

GET /history/<conversation_id> returns the saved turns of one conversation, so
the frontend can reload a past chat. Listing all of a user's conversations (the
"recents" sidebar) needs a logged-in identity to scope by, so it arrives with
auth in build step 4; for now a conversation is fetched by its own opaque id.
"""

from fastapi import APIRouter, HTTPException, Request

from .. import auth, store
from ..db import is_enabled, new_session

router = APIRouter()


@router.get("/conversations")
def list_conversations(request: Request):
    """The signed-in user's past conversations, newest first (the recents list).

    Scoped by the session cookie: signed out (or no database) simply returns an
    empty list, so the frontend renders an empty sidebar rather than an error.
    """
    user_id = auth.read_session(request.cookies.get(auth.SESSION_COOKIE))
    if not user_id or not is_enabled():
        return {"conversations": []}

    db = new_session()
    try:
        convos = store.list_user_conversations(db, user_id)
        return {
            "conversations": [
                {
                    "id": c.id,
                    "title": c.title or "New conversation",
                    "created_at": c.created_at.isoformat(),
                }
                for c in convos
            ]
        }
    finally:
        db.close()


@router.get("/history/{conversation_id}")
def get_history(conversation_id: str):
    if not is_enabled():
        # No DATABASE_URL configured: persistence is off, so there is nothing to
        # read. 503 says "the server can't do this right now", not "not found".
        raise HTTPException(status_code=503, detail="History is not configured.")

    db = new_session()
    try:
        messages = store.conversation_messages(db, conversation_id)
        if not messages:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        return {
            "conversation_id": conversation_id,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
        }
    finally:
        db.close()
