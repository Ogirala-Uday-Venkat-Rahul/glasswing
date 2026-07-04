// Renders the agent's live timeline: one row per Step as it streams in.
//
// The whole point of Glasswing is that you SEE the agent work, so each kind of
// step gets its own look. The final answer is pulled out and shown prominently
// below the timeline; everything else (thinking, tool calls, tool results,
// errors) is the transparency trail that leads up to it.

const TOOL_LABELS = {
  calculator: "Calculator",
  web_search: "Web search",
  fetch_url: "Read page",
  current_datetime: "Current date/time",
  convert: "Unit convert",
};

function toolName(name) {
  return TOOL_LABELS[name] || name;
}

function StepRow({ step }) {
  if (step.type === "thinking") {
    return (
      <div className="step step-thinking">
        <span className="step-tag">thinking</span>
        <span className="step-body">{step.content}</span>
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
          <span className="answer-tag">answer</span>
          <div className="answer-body">{answer.content}</div>
        </div>
      )}
    </div>
  );
}
