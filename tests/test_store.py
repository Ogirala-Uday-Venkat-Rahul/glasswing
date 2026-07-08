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


def test_delete_conversation_removes_it_and_its_messages(db):
    store.create_conversation(db, "c1", user_id="u1", title="hello")
    store.add_message(db, "c1", "user", "hi", image_key="uploads/u1/pic.png")
    store.add_message(db, "c1", "assistant", "hello there")
    db.commit()

    keys = store.delete_conversation(db, "c1", user_id="u1")
    db.commit()

    # It reports the attached image keys (for blob cleanup) and the rows are gone.
    assert keys == ["uploads/u1/pic.png"]
    assert store.conversation_messages(db, "c1") == []
    assert store.list_user_conversations(db, "u1") == []


def test_delete_conversation_is_scoped_to_the_owner(db):
    store.create_conversation(db, "c1", user_id="owner")
    store.add_message(db, "c1", "user", "mine")
    db.commit()

    # A different user can't delete it: nothing happens and it still exists.
    assert store.delete_conversation(db, "c1", user_id="intruder") is None
    assert [m.content for m in store.conversation_messages(db, "c1")] == ["mine"]


def test_delete_missing_conversation_returns_none(db):
    assert store.delete_conversation(db, "nope", user_id="u1") is None


def test_conversation_has_image_tracks_attachments(db):
    store.create_conversation(db, "text-only")
    store.add_message(db, "text-only", "user", "hi")
    store.create_conversation(db, "with-pic")
    store.add_message(db, "with-pic", "user", "look", image_key="uploads/u1/p.png")
    store.add_message(db, "with-pic", "assistant", "a jersey")
    db.commit()

    assert store.conversation_has_image(db, "with-pic") is True
    assert store.conversation_has_image(db, "text-only") is False
    assert store.conversation_has_image(db, "missing") is False
