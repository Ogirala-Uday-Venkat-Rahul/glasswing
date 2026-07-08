"""Read endpoint for a stored conversation (build step 3).

GET /history/<conversation_id> returns the saved turns of one conversation, so
the frontend can reload a past chat. Listing all of a user's conversations (the
"recents" sidebar) needs a logged-in identity to scope by, so it arrives with
auth in build step 4; for now a conversation is fetched by its own opaque id.
"""

from fastapi import APIRouter, HTTPException, Request

from .. import auth, storage, store
from ..db import is_enabled, new_session

router = APIRouter()


def _message_json(m):
    """Shape a stored message for the client, presigning any attached image.

    The database keeps only the storage object key; here we turn it into a short-lived
    view URL so the browser can redisplay the picture on reload. If storage isn't
    configured (or presigning fails), we simply omit the image rather than error.
    """
    data = {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
    if m.image_key and storage.is_enabled():
        try:
            data["image_url"] = storage.view_url(m.image_key)
        except Exception as exc:  # noqa: BLE001 - a missing blob shouldn't 500 a reload
            print(f"[history] could not presign image {m.image_key}: {exc}")
    return data


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


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, request: Request):
    """Delete one of the signed-in user's conversations, and its images.

    Requires a session (deleting is owner-only) and scopes the delete to that
    user, so the id in the URL can only ever remove the caller's own chat. The
    database rows go first (in a transaction); the image blobs are then removed
    best-effort -- a failed blob delete leaves an orphan but never fails the
    request, since the conversation is already gone.
    """
    user_id = auth.read_session(request.cookies.get(auth.SESSION_COOKIE))
    if not user_id:
        raise HTTPException(status_code=401, detail="Sign in to delete a conversation.")
    if not is_enabled():
        raise HTTPException(status_code=503, detail="History is not configured.")

    db = new_session()
    try:
        image_keys = store.delete_conversation(db, conversation_id, user_id)
        if image_keys is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        db.commit()
    finally:
        db.close()

    if storage.is_enabled():
        for key in image_keys:
            try:
                storage.delete_object(key)
            except Exception as exc:  # noqa: BLE001 - orphaned blob is harmless
                print(f"[history] could not delete blob {key}: {exc}")

    return {"deleted": conversation_id}


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
            "messages": [_message_json(m) for m in messages],
        }
    finally:
        db.close()
