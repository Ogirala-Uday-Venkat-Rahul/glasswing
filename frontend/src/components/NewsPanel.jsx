import { useState, useEffect } from "react";
import { getNews } from "../api.js";

// An opt-in "Today's headlines" panel that lives under the recents list. Off by
// default and remembered in localStorage, so it never surprises a first-time
// visitor and never spends a Serper call unless asked for. When on, it pulls a
// few top headlines and turns each into a one-click prompt: clicking sends it to
// the agent, which searches it and answers -- the news feature and the chat are
// the same loop, so there's no separate "news reader" to build or maintain.
//
// It owns its own small state (the toggle, the fetched list) because news is
// independent of the conversation; onAsk is the one hook back into Workspace,
// which turns a headline into a real agent turn.
export default function NewsPanel({ onAsk, busy }) {
  const [on, setOn] = useState(() => localStorage.getItem("gw-news") === "1");
  const [headlines, setHeadlines] = useState([]);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  // Persist the choice, and (re)fetch whenever the panel is switched on. The
  // cancelled flag drops a late response if the panel is closed mid-request.
  useEffect(() => {
    localStorage.setItem("gw-news", on ? "1" : "0");
    if (!on) return;
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    getNews()
      .then((items) => !cancelled && setHeadlines(items))
      .catch(() => !cancelled && setFailed(true))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [on]);

  return (
    <div className="news">
      <button
        type="button"
        className="news-toggle"
        onClick={() => setOn((v) => !v)}
        aria-pressed={on}
      >
        <span>Today's headlines</span>
        <span className={"news-switch" + (on ? " is-on" : "")} aria-hidden="true" />
      </button>

      {on && (
        <div className="news-list">
          {loading && <p className="news-note">Loading headlines…</p>}
          {failed && <p className="news-note">Couldn't load headlines right now.</p>}
          {!loading && !failed && headlines.length === 0 && (
            <p className="news-note">No headlines available.</p>
          )}
          {!loading &&
            !failed &&
            headlines.map((h, i) => (
              <button
                key={i}
                type="button"
                className="news-item"
                disabled={busy}
                title={[h.title, h.source].filter(Boolean).join(" — ")}
                onClick={() =>
                  onAsk(`Summarize this news and why it matters: "${h.title}"`)
                }
              >
                <span className="news-item-title">{h.title}</span>
                <span className="news-item-meta">
                  {[h.source, h.date].filter(Boolean).join(" · ")}
                </span>
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
