"""Query helpers for conversation history (build step 3).

Thin functions over the models so the routes and the /chat endpoint never write
SQLAlchemy by hand. Each takes an already-open Session, which keeps them trivial
to unit test against a throwaway in-memory database (see tests/test_store.py).
Uses the SQLAlchemy 2.0 select() style throughout.
"""

from sqlalchemy import select

from .models import Conversation, Memory, Message, User

# How many remembered facts we load back into the agent's context per run. A cap
# so a chatty user's memory can't grow the prompt without bound; newest kept.
MAX_MEMORIES = 40

# How many past messages we replay into the agent. A conversation can grow
# without bound, and the loop re-sends its whole context on every model call, so
# we feed back only the most recent slice rather than the entire history.
MAX_HISTORY_MESSAGES = 20


def add_memory(db, user_id, content):
    """Save one durable fact about a user. Commits itself (called mid-agent-run).

    Skips an exact duplicate so the agent re-stating a fact it already knows
    doesn't pile up identical rows. Light on purpose -- near-duplicates ("likes
    ramen" vs "loves ramen") still both save; real dedup would need embeddings,
    which is more than a portfolio memory needs.
    """
    content = (content or "").strip()
    if not content:
        return None
    exists = db.scalars(
        select(Memory).where(Memory.user_id == user_id, Memory.content == content)
    ).first()
    if exists:
        return exists
    mem = Memory(user_id=user_id, content=content)
    db.add(mem)
    db.commit()
    return mem


def list_memories(db, user_id):
    """A user's remembered facts as plain strings, newest first, capped.

    Returned oldest-first so the injected context reads in the order they were
    learned; we take the newest MAX_MEMORIES then reverse.
    """
    stmt = (
        select(Memory)
        .where(Memory.user_id == user_id)
        .order_by(Memory.id.desc())
        .limit(MAX_MEMORIES)
    )
    recent = list(db.scalars(stmt))
    recent.reverse()
    return [m.content for m in recent]


def get_or_create_user(db, email):
    """Find the user with this email, or create one. Not committed -- caller commits.

    This is the "upsert" the OAuth callback needs: the first time someone signs in
    we make their row; every time after we return the same row. We key on email
    because Google guarantees it and User.email is unique, so a returning user maps
    to exactly one account.
    """
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None:
        user = User(email=email)
        db.add(user)
        db.flush()  # populate user.id now so the caller can use it before commit
    return user


def list_user_conversations(db, user_id):
    """A user's conversations, newest first -- the data behind the recents list.

    Scoped to one user_id so people only ever see their own chats. Returns the
    Conversation rows; the route shapes them into JSON.
    """
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
    )
    return list(db.scalars(stmt))


def delete_conversation(db, conversation_id, user_id):
    """Delete a conversation and its messages, if it belongs to this user.

    Scoped by user_id: the conversation id travels in the URL, so the id alone
    must not be enough to delete -- we only delete a row that both matches the id
    AND is owned by the caller, so no one can wipe someone else's chat by guessing.
    Returns the storage keys of any attached images (so the caller can clean up
    those blobs), or None when there was nothing to delete (missing or not theirs).
    The delete cascades to the messages via the relationship. Not committed here.
    """
    convo = db.scalars(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    ).first()
    if convo is None:
        return None
    image_keys = [m.image_key for m in convo.messages if m.image_key]
    db.delete(convo)  # cascade="all, delete-orphan" removes the messages too
    return image_keys


def create_conversation(db, conversation_id, user_id=None, title=None):
    """Insert a new conversation row. Not committed here -- the caller commits."""
    convo = Conversation(id=conversation_id, user_id=user_id, title=title)
    db.add(convo)
    return convo


def add_message(db, conversation_id, role, content, image_key=None):
    """Append one turn. Not committed here -- the caller commits.

    image_key, when set, is the storage pointer for a picture the user attached to this
    message (see backend/storage.py). Stored so a reloaded conversation can show
    the image again; the agent's replayed history stays text-only.
    """
    msg = Message(conversation_id=conversation_id, role=role, content=content, image_key=image_key)
    db.add(msg)
    return msg


def conversation_messages(db, conversation_id):
    """Every message in a conversation, oldest first (for the history endpoint)."""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id)
    )
    return list(db.scalars(stmt))


def load_history(db, conversation_id):
    """Prior turns as [{"role", "content"}] to replay into the agent.

    Returns the most recent MAX_HISTORY_MESSAGES messages in chat order. We query
    newest-first with a LIMIT (so the database does the trimming, not Python) then
    reverse back to oldest-first, which is the order the model expects.
    """
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(MAX_HISTORY_MESSAGES)
    )
    recent = list(db.scalars(stmt))
    recent.reverse()
    return [{"role": m.role, "content": m.content} for m in recent]
