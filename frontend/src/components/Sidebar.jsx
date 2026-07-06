// The recents list: the signed-in user's past conversations, newest first.
// Clicking one loads it into the pane; "New chat" starts a fresh thread. The
// active conversation is highlighted so it's clear which one you're looking at.
//
// Purely presentational -- Workspace owns the data and the handlers.

export default function Sidebar({ conversations, activeId, onSelect, onNew, busy }) {
  return (
    <aside className="sidebar">
      <button className="new-chat-btn" onClick={onNew} disabled={busy}>
        + New chat
      </button>

      <div className="recents">
        {conversations.length === 0 ? (
          <p className="recents-empty">No conversations yet.</p>
        ) : (
          conversations.map((c) => (
            <button
              key={c.id}
              className={"recent" + (c.id === activeId ? " active" : "")}
              onClick={() => onSelect(c.id)}
              disabled={busy}
              title={c.title}
            >
              {c.title}
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
