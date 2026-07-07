"""Database models: the relational shape of a Glasswing conversation.

Three tables in one parent-to-child chain:

    User  ->  Conversation  ->  Message

A user owns many conversations; a conversation holds many messages (the turns).
We persist only the turns the user sees -- their message and the agent's final
answer -- never the tool-call/tool-result scratch the agent produces while
working. That internal reasoning is streamed live to the UI for transparency,
but it is transient and re-derivable, so it does not belong in the durable
record and would only bloat the table and the context we replay.

user_id is nullable on purpose. Build step 3 has no login yet, so conversations
are created unowned; build step 4 (Google OAuth) fills in the owner. Defining
the column now means auth is a data change, not a schema migration later.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


def _uuid() -> str:
    """An opaque, unguessable id. Used for rows whose id appears in a URL."""
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    # A uuid, because this id is handed to the client and used in /history/<id>;
    # a guessable sequential id would let anyone walk other people's chats.
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User | None"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )


class Memory(Base):
    """A durable fact about a user, remembered across all their conversations.

    This is what makes the agent feel like it *knows* you rather than starting
    cold every chat. The agent writes rows here through its `remember` tool when
    you share something worth keeping (your name, preferences, ongoing work); at
    the start of every run we load them back and put them in the agent's context.

    Scoped to a user, not a conversation -- that is the whole point. A fact you
    told the agent in one chat is available in the next. No login, no memory.
    """

    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Message(Base):
    __tablename__ = "messages"

    # An autoincrementing integer, not a uuid: it gives a natural insertion order
    # to sort by. We deliberately do NOT order by created_at -- a clock (Windows
    # especially) can stamp two fast writes with the same value, which would make
    # ordering ambiguous. The id is monotonic, so it never can. It stays internal
    # (never exposed in a URL), so a sequential id is fine here.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text)
    # The R2 object key for an image attached to this turn, if any. Only the
    # pointer lives in the database; the bytes live in R2 (see backend/storage.py).
    # Null for almost every row -- assistant turns and text-only user turns.
    image_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
