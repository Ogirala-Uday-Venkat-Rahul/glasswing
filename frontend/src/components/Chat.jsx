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
  {
    tag: "Convert + Calculator",
    prompt: "How many miles is a 42.195 km marathon, and at a 10-min/mile pace how long would it take?",
  },
  {
    tag: "Live Google Search",
    prompt: "What was SpaceX's most recent launch?",
  },
  {
    tag: "Real-time Clock",
    prompt: "What's the date and time right now?",
  },
];

export default function Chat({
  exchanges,
  busy,
  input,
  onInputChange,
  onSubmit,
  onStop,
  onExample,
  attachedImage,
  onPickImage,
  onClearImage,
}) {
  const bottomRef = useRef(null);

  // Keep the newest step in view as the timeline grows.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [exchanges]);

  function handleExport() {
    if (!exchanges || exchanges.length === 0) return;

    const lines = [
      "# Glasswing Agent Research Session",
      `*Generated on ${new Date().toISOString().replace("T", " ").slice(0, 19)} UTC*`,
      "",
      "---",
      "",
    ];

    exchanges.forEach((ex, idx) => {
      lines.push(`## Turn ${idx + 1}`);
      lines.push(`**Prompt:** ${ex.question}`);
      if (ex.image) {
        lines.push(`*(Attached image analyzed)*`);
      }
      lines.push("");

      const steps = ex.steps || [];
      const nonAnswerSteps = steps.filter((s) => s.type !== "final_answer");
      if (nonAnswerSteps.length > 0) {
        lines.push("### Execution & Reasoning Trace:");
        nonAnswerSteps.forEach((s) => {
          if (s.type === "thinking") {
            lines.push(`- *Thinking:* ${s.content}`);
          } else if (s.type === "tool_call") {
            const args = s.args ? JSON.stringify(s.args) : "";
            lines.push(`- **Tool Call (${s.tool}):** \`${args}\``);
          } else if (s.type === "tool_result") {
            lines.push(`- **Result (${s.tool}):** \`${s.content}\``);
          } else if (s.type === "error") {
            lines.push(`- **Error:** ${s.content}`);
          }
        });
        lines.push("");
      }

      const answer = steps.find((s) => s.type === "final_answer");
      if (answer) {
        lines.push("### Final Answer:");
        lines.push(answer.content);
        lines.push("");
      }
      lines.push("---");
      lines.push("");
    });

    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `glasswing-research-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="chat">
      {exchanges.length > 0 && (
        <div className="chat-actions">
          <button
            type="button"
            className="export-btn"
            onClick={handleExport}
            title="Download conversation transcript and reasoning steps as Markdown"
          >
            <ExportIcon />
            Export (.md)
          </button>
        </div>
      )}

      <div className="exchanges">
        {exchanges.length === 0 && (
          <div className="empty">
            <p className="empty-lead">
              Ask a question and watch the agent think, use its tools, and answer.
            </p>
            <div className="examples">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex.prompt}
                  type="button"
                  className="example"
                  onClick={() => onExample(ex.prompt)}
                  disabled={busy}
                >
                  <span className="example-tag">{ex.tag}</span>
                  <span className="example-text">{ex.prompt}</span>
                </button>
              ))}
            </div>
          </div>
        )}
        {exchanges.map((ex, i) => (
          <div key={i} className="exchange">
            <div className="user-turn">
              <div className="user-bubble">
                <span className="user-badge" aria-hidden="true">You</span>
                <span className="user-text">{ex.question}</span>
              </div>
            </div>
            {ex.image && (
              <img className="exchange-image" src={ex.image} alt="Attached by the user" />
            )}
            <StepTimeline steps={ex.steps} fromImage={!!ex.image} />
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
        <div className="composer-bar">
          {attachedImage ? (
            <div
              className="attach-preview"
              title="Attached image. Click × to remove."
            >
              <img src={attachedImage} alt="Attachment preview" />
              <button
                type="button"
                className="attach-remove"
                onClick={onClearImage}
                aria-label="Remove attached image"
              >
                ×
              </button>
            </div>
          ) : (
            <label className="attach-btn" title="Attach an image">
              <input
                type="file"
                accept="image/*"
                hidden
                disabled={busy}
                onChange={(e) => {
                  onPickImage(e.target.files[0]);
                  e.target.value = ""; // let the same file be re-picked later
                }}
              />
              <ImageIcon />
            </label>
          )}
          <input
            type="text"
            className="composer-input"
            value={input}
            placeholder={busy ? "Agent is working… click Stop to halt" : "Ask anything or attach a picture…"}
            onChange={(e) => onInputChange(e.target.value)}
            disabled={busy}
          />
          {busy ? (
            <button
              type="button"
              className="composer-btn stop"
              onClick={onStop}
              title="Stop agent execution"
            >
              <span className="stop-sq" />
              <span>Stop</span>
            </button>
          ) : (
            <button
              type="submit"
              className="composer-btn send"
              disabled={!input.trim() && !attachedImage}
              title="Send message"
            >
              <SendIcon />
            </button>
          )}
        </div>
      </form>
    </div>
  );
}

function SendIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="12" y1="19" x2="12" y2="5" />
      <polyline points="5 12 12 5 19 12" />
    </svg>
  );
}

function ExportIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

// A simple picture glyph for the attach button (inline so there's no asset load).
function ImageIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="2" />
      <circle cx="8.5" cy="8.5" r="1.5" fill="currentColor" />
      <path d="M21 15l-5-5L5 21" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}
