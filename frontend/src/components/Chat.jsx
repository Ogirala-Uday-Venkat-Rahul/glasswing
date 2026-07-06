import { useRef, useEffect } from "react";
import StepTimeline from "./StepTimeline.jsx";

// The message pane: renders the current conversation's exchanges and the
// composer. It is purely presentational now -- all conversation state (which
// chat is active, its exchanges, streaming) lives in Workspace, so the sidebar
// and this pane stay in sync. Each exchange is one turn: the question plus the
// steps the agent streamed answering it.

export default function Chat({ exchanges, busy, input, onInputChange, onSubmit }) {
  const bottomRef = useRef(null);

  // Keep the newest step in view as the timeline grows.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [exchanges]);

  return (
    <div className="chat">
      <div className="exchanges">
        {exchanges.length === 0 && (
          <div className="empty">
            Ask a question and watch the agent think, use its tools, and answer.
          </div>
        )}
        {exchanges.map((ex, i) => (
          <div key={i} className="exchange">
            <div className="question">{ex.question}</div>
            <StepTimeline steps={ex.steps} />
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form className="composer" onSubmit={onSubmit}>
        <input
          type="text"
          value={input}
          placeholder={busy ? "Agent is working…" : "Ask anything…"}
          onChange={(e) => onInputChange(e.target.value)}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          {busy ? "…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
