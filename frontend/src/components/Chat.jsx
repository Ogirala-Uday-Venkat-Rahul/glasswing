import { useState, useRef, useEffect } from "react";
import { streamChat } from "../api.js";
import StepTimeline from "./StepTimeline.jsx";

// One turn of conversation: the question the user asked, and the list of steps
// the agent produced answering it. Steps accumulate live as they stream in.
//
// This is still a stateless demo: nothing is saved, and each question is its own
// exchange. Conversation memory (remembering earlier turns) is a later build
// step; this component is written so that adding it means feeding prior turns
// into the request, not reworking the UI.

export default function Chat() {
  const [input, setInput] = useState("");
  const [exchanges, setExchanges] = useState([]);
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef(null);

  // Keep the newest step in view as the timeline grows.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [exchanges]);

  async function ask(question) {
    setBusy(true);
    // Add the new exchange with an empty step list, remember where it is.
    const index = exchanges.length;
    setExchanges((prev) => [...prev, { question, steps: [] }]);

    try {
      for await (const step of streamChat(question)) {
        // Append each step to this exchange as it arrives.
        setExchanges((prev) => {
          const next = [...prev];
          next[index] = { ...next[index], steps: [...next[index].steps, step] };
          return next;
        });
      }
    } catch (err) {
      setExchanges((prev) => {
        const next = [...prev];
        const errStep = { type: "error", content: `Could not reach the agent: ${err.message}` };
        next[index] = { ...next[index], steps: [...next[index].steps, errStep] };
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || busy) return;
    setInput("");
    ask(question);
  }

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
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          {busy ? "…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
