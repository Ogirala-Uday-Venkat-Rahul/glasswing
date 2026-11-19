// Renders the agent's live timeline: one row per Step as it streams in.
//
// The whole point of Glasswing is that you SEE the agent work, so each kind of
// step gets its own look. The final answer is pulled out and shown prominently
// below the timeline; everything else (thinking, tool calls, tool results,
// errors) is the transparency trail that leads up to it.

import { useState } from "react";
import Markdown from "./Markdown.jsx";

const TOOL_LABELS = {
  calculator: "Calculator",
  web_search: "Web search",
  fetch_url: "Read page",
  current_datetime: "Current date/time",
  convert: "Unit convert",
  remember: "Remember",
};

function toolName(name) {
  return TOOL_LABELS[name] || name;
}

// Copies the answer text to the clipboard, with a brief "Copied" confirmation.
function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable -- nothing to do */
    }
  }

  return (
    <button type="button" className="copy-btn" onClick={copy} title="Copy response">
      {copied ? (
        <>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span>Copied</span>
        </>
      ) : (
        <>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
          <span>Copy</span>
        </>
      )}
    </button>
  );
}

function StepRow({ step }) {
  if (step.type === "thinking") {
    return (
      <div className="step step-thinking">
        <span className="step-tag">
          <svg className="step-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2a8 8 0 0 0-8 8c0 3 2 5.5 4 7v3h8v-3c2-1.5 4-4 4-7a8 8 0 0 0-8-8z" />
            <line x1="10" y1="22" x2="14" y2="22" />
          </svg>
          thinking
        </span>
        <span className="step-body"><Markdown text={step.content} /></span>
      </div>
    );
  }

  if (step.type === "tool_call") {
    const args = step.args ? JSON.stringify(step.args) : "";
    return (
      <div className="step step-call">
        <span className="step-tag">
          <svg className="step-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
          </svg>
          using tool
        </span>
        <span className="step-body">
          <strong>{toolName(step.tool)}</strong>
          {args && <code className="step-args">{args}</code>}
        </span>
      </div>
    );
  }

  if (step.type === "tool_result") {
    // Extract web domains for clean source badges if it's search or fetch
    const rawUrls = (step.content || "").match(/https?:\/\/[^\s\)\"\'\<\>]+/g) || [];
    const uniqueDomains = Array.from(new Set(rawUrls.map(u => {
      try { return { domain: new URL(u).hostname.replace(/^www\./, ""), url: u }; } catch { return null; }
    }))).filter(Boolean);

    return (
      <div className="step step-result">
        <span className="step-tag">
          <svg className="step-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          result
        </span>
        <span className="step-body">
          <span className="step-result-from">{toolName(step.tool)} returned</span>
          <code className="step-result-text">{step.content}</code>
          {uniqueDomains.length > 0 && (
            <div className="source-badges">
              {uniqueDomains.slice(0, 4).map(({ domain, url }) => (
                <a
                  key={url}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="source-badge"
                  title={url}
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="2" y1="12" x2="22" y2="12" />
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                  </svg>
                  <span>{domain}</span>
                  <span className="source-arrow">↗</span>
                </a>
              ))}
            </div>
          )}
        </span>
      </div>
    );
  }

  if (step.type === "error") {
    return (
      <div className="step step-error">
        <span className="step-tag">
          <svg className="step-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          error
        </span>
        <span className="step-body">{step.content}</span>
      </div>
    );
  }

  return null; // final_answer is rendered separately by the parent
}

export default function StepTimeline({ steps, fromImage = false }) {
  const trail = steps.filter((s) => s.type !== "final_answer");
  const answer = steps.find((s) => s.type === "final_answer");
  // Expand reasoning by default while running; allow toggling when finished
  const [trailOpen, setTrailOpen] = useState(true);

  // Tools used summary
  const toolNames = Array.from(new Set(trail.filter(s => s.tool).map(s => toolName(s.tool))));

  return (
    <div className="timeline">
      {trail.length > 0 && answer && (
        <button
          type="button"
          className="trail-toggle"
          onClick={() => setTrailOpen(!trailOpen)}
          title="Toggle reasoning steps"
        >
          <span className="trail-toggle-left">
            <span className={`trail-arrow ${trailOpen ? "open" : ""}`}>›</span>
            <span>Reasoning trace · {trail.length} {trail.length === 1 ? "step" : "steps"}</span>
            {toolNames.length > 0 && (
              <span className="trail-tools">({toolNames.join(", ")})</span>
            )}
          </span>
          <span className="trail-toggle-action">{trailOpen ? "Collapse" : "Expand"}</span>
        </button>
      )}

      {(trailOpen || !answer) && trail.map((step, i) => (
        <StepRow key={i} step={step} />
      ))}

      {answer && (
        <div className="answer">
          <div className="answer-body">
            <Markdown text={answer.content} />
          </div>
          <div className="answer-actions">
            {fromImage && (
              <span className="answer-source" title="This answer was read from the image you attached">
                <ImageGlyph />
                Read from your image
              </span>
            )}
            <CopyButton text={answer.content} />
          </div>
        </div>
      )}
    </div>
  );
}

// A tiny picture glyph for the "read from your image" badge (inline, no asset).
function ImageGlyph() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="2" />
      <circle cx="8.5" cy="8.5" r="1.5" fill="currentColor" />
      <path d="M21 15l-5-5L5 21" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}
