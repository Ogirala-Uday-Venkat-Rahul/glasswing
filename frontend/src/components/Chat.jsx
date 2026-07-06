import { useState, useRef, useEffect } from "react";
import { streamChat } from "../api.js";
import StepTimeline from "./StepTimeline.jsx";

// One turn of conversation: the question the user asked, and the list of steps
// the agent produced answering it. Steps accumulate live as they stream in.
//
// Turns belong to a conversation. The backend mints a conversation_id on the
// first turn (delivered as the stream's "meta" event) and remembers it here in a
// ref; every later turn sends that id back, so the server replays the earlier
// turns into the agent and it has memory. "New chat" forgets the id to start a
// fresh thread. (Actual persistence needs DATABASE_URL set on the backend; with
// no database the id still round-trips but there is nothing to replay.)

export default function Chat() {
  const [input, setInput] = useState("");
  const [exchanges, setExchanges] = useState([]);
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef(null);
  // Survives across renders without causing one; read synchronously inside ask().
  const conversationId = useRef(null);

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
      for await (const step of streamChat(question, {
        conversationId: conversationId.current,
        onMeta: (meta) => {
          conversationId.current = meta.conversation_id;
        },
      })) {
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

  function newChat() {
    // Forget the thread and clear the screen; the next turn mints a fresh id.
    conversationId.current = null;
    setExchanges([]);
    setInput("");
  }

  return (
    <div className="chat">
      <div className="toolbar">
        <button
          type="button"
          className="new-chat"
          onClick={newChat}
          disabled={busy || exchanges.length === 0}
        >
          New chat
        </button>
      </div>
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
