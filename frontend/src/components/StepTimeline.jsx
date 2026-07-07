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
// A staple of any chat tool -- people want the answer, not to reselect it. The
// clipboard API can be blocked (permissions, insecure origin); we just swallow
// that rather than surface an error for a convenience action.
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
    <button type="button" className="copy-btn" onClick={copy} title="Copy answer">
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function StepRow({ step }) {
  if (step.type === "thinking") {
    return (
      <div className="step step-thinking">
        <span className="step-tag">thinking</span>
        <span className="step-body"><Markdown text={step.content} /></span>
      </div>
    );
  }

  if (step.type === "tool_call") {
    const args = step.args ? JSON.stringify(step.args) : "";
    return (
      <div className="step step-call">
        <span className="step-tag">using tool</span>
        <span className="step-body">
          <strong>{toolName(step.tool)}</strong>
          {args && <code className="step-args">{args}</code>}
        </span>
      </div>
    );
  }

  if (step.type === "tool_result") {
    return (
      <div className="step step-result">
        <span className="step-tag">result</span>
        <span className="step-body">
          <span className="step-result-from">{toolName(step.tool)} returned</span>
          <code className="step-result-text">{step.content}</code>
        </span>
      </div>
    );
  }

  if (step.type === "error") {
    return (
      <div className="step step-error">
        <span className="step-tag">error</span>
        <span className="step-body">{step.content}</span>
      </div>
    );
  }

  return null; // final_answer is rendered separately by the parent
}

export default function StepTimeline({ steps }) {
  const trail = steps.filter((s) => s.type !== "final_answer");
  const answer = steps.find((s) => s.type === "final_answer");

  return (
    <div className="timeline">
      {trail.map((step, i) => (
        <StepRow key={i} step={step} />
      ))}
      {answer && (
        <div className="answer">
          <div className="answer-head">
            <span className="answer-tag">answer</span>
            <CopyButton text={answer.content} />
          </div>
          <div className="answer-body"><Markdown text={answer.content} /></div>
        </div>
      )}
    </div>
  );
}
