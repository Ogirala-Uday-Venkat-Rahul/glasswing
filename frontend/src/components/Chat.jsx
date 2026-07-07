import { useRef, useEffect } from "react";
import StepTimeline from "./StepTimeline.jsx";

// The message pane: renders the current conversation's exchanges and the
// composer. It is purely presentational now -- all conversation state (which
// chat is active, its exchanges, streaming) lives in Workspace, so the sidebar
// and this pane stay in sync. Each exchange is one turn: the question plus the
// steps the agent streamed answering it.

// Starter prompts for an empty chat. Each is chosen to exercise a different
// tool, so a first-time visitor sees the agent reach for the right one: unit
// conversion + arithmetic, a live web search, and the clock.
const EXAMPLES = [
  "How many miles is a 42.195 km marathon, and at a 10-min/mile pace how long would it take?",
  "What was SpaceX's most recent launch?",
  "What's the date and time right now?",
];

export default function Chat({ exchanges, busy, input, onInputChange, onSubmit, onExample }) {
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
            <p className="empty-lead">
              Ask a question and watch the agent think, use its tools, and answer.
            </p>
            <div className="examples">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  className="example"
                  onClick={() => onExample(ex)}
                  disabled={busy}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}
        {exchanges.map((ex, i) => (
          <div key={i} className="exchange">
            <div className="question">{ex.question}</div>
            <StepTimeline steps={ex.steps} />
            {ex.streaming && (
              // The live typewriter feed: the model's output as it streams,
              // before the committed step (thinking or answer) replaces it.
              <div className="step step-thinking step-streaming">
                <span className="step-tag">writing</span>
                <span className="step-body">
                  {ex.streaming}
                  <span className="stream-cursor" />
                </span>
              </div>
            )}
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
