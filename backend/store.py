"""Query helpers for conversation history (build step 3).

Thin functions over the models so the routes and the /chat endpoint never write
SQLAlchemy by hand. Each takes an already-open Session, which keeps them trivial
to unit test against a throwaway in-memory database (see tests/test_store.py).
Uses the SQLAlchemy 2.0 select() style throughout.
"""

from sqlalchemy import select

from .models import Conversation, Message, User

# How many past messages we replay into the agent. A conversation can grow
# without bound, and the loop re-sends its whole context on every model call, so
# we feed back only the most recent slice rather than the entire history.
MAX_HISTORY_MESSAGES = 20


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


def create_conversation(db, conversation_id, user_id=None, title=None):
    """Insert a new conversation row. Not committed here -- the caller commits."""
    convo = Conversation(id=conversation_id, user_id=user_id, title=title)
    db.add(convo)
    return convo


def add_message(db, conversation_id, role, content):
    """Append one turn. Not committed here -- the caller commits."""
    msg = Message(conversation_id=conversation_id, role=role, content=content)
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
