// The recents list: the signed-in user's past conversations, newest first.
// Clicking one loads it into the pane; "New chat" starts a fresh thread. The
// active conversation is highlighted so it's clear which one you're looking at.
//
// Purely presentational -- Workspace owns the data and the handlers. The one
// exception is the opt-in news panel below, which owns its own fetch (news is
// independent of conversation state) and reaches back through onAskHeadline.

import NewsPanel from "./NewsPanel.jsx";

// A compact "how long ago" label from an ISO timestamp, so the list reads as a
// history and not just a stack of titles. Falls back to a plain date past a week.
function relativeTime(iso) {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (secs < 60) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function Sidebar({ conversations, activeId, onSelect, onNew, onAskHeadline, busy }) {
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
              <span className="recent-title">{c.title}</span>
              <span className="recent-time">{relativeTime(c.created_at)}</span>
            </button>
          ))
        )}
      </div>

      <NewsPanel onAsk={onAskHeadline} busy={busy} />
    </aside>
  );
}
