"""Offline tests for the history store, against in-memory SQLite.

No Postgres needed: an in-memory SQLite database runs the same SQLAlchemy models
and query logic, so we can prove create / load / ordering / isolation anywhere,
including CI. The live Neon connection is verified separately once its URL exists.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import store
from backend.models import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_messages_persist_in_insertion_order(db):
    store.create_conversation(db, "c1", title="hello")
    store.add_message(db, "c1", "user", "hi")
    store.add_message(db, "c1", "assistant", "hello there")
    store.add_message(db, "c1", "user", "bye")
    db.commit()

    msgs = store.conversation_messages(db, "c1")
    assert [m.role for m in msgs] == ["user", "assistant", "user"]
    assert [m.content for m in msgs] == ["hi", "hello there", "bye"]


def test_load_history_returns_role_content_dicts(db):
    store.create_conversation(db, "c1")
    store.add_message(db, "c1", "user", "one")
    store.add_message(db, "c1", "assistant", "two")
    db.commit()

    assert store.load_history(db, "c1") == [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
    ]


def test_load_history_caps_to_recent_messages_in_order(db, monkeypatch):
    monkeypatch.setattr(store, "MAX_HISTORY_MESSAGES", 3)
    store.create_conversation(db, "c1")
    for i in range(5):
        store.add_message(db, "c1", "user", f"m{i}")
    db.commit()

    # The three most recent, still oldest-first for the model.
    assert [h["content"] for h in store.load_history(db, "c1")] == ["m2", "m3", "m4"]


def test_history_is_isolated_per_conversation(db):
    store.create_conversation(db, "a")
    store.create_conversation(db, "b")
    store.add_message(db, "a", "user", "in a")
    store.add_message(db, "b", "user", "in b")
    db.commit()

    assert [m.content for m in store.conversation_messages(db, "a")] == ["in a"]
    assert store.load_history(db, "b") == [{"role": "user", "content": "in b"}]


def test_unknown_conversation_is_empty(db):
    assert store.conversation_messages(db, "missing") == []
    assert store.load_history(db, "missing") == []
