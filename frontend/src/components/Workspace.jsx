import { useState, useEffect } from "react";
import Sidebar from "./Sidebar.jsx";
import Chat from "./Chat.jsx";
import { streamChat, listConversations, getConversation } from "../api.js";

// The signed-in workspace: recents sidebar on the left, the active conversation
// on the right. This component owns all conversation state so the two stay in
// sync -- which chat is active, its exchanges on screen, and the streaming of a
// new turn. Chat and Sidebar are presentational and just render what they're given.

// A saved conversation is only the user/assistant turns (the agent's tool steps
// are transient and never stored). So to redisplay one we turn each stored
// assistant message into a single "final_answer" step, which is exactly what the
// timeline renders as the answer.
function toExchanges(messages) {
  const out = [];
  for (const m of messages) {
    if (m.role === "user") {
      out.push({ question: m.content, steps: [] });
    } else {
      if (out.length === 0) out.push({ question: "", steps: [] });
      out[out.length - 1].steps.push({ type: "final_answer", content: m.content });
    }
  }
  return out;
}

export default function Workspace() {
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null); // null = a fresh, unsaved chat
  const [exchanges, setExchanges] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  // Load the recents list once on mount.
  useEffect(() => {
    refreshConversations();
  }, []);

  async function refreshConversations() {
    setConversations(await listConversations());
  }

  async function ask(question) {
    setBusy(true);
    const index = exchanges.length; // where this turn's exchange will live
    const wasNew = activeId === null;
    setExchanges((prev) => [...prev, { question, steps: [], streaming: "" }]);

    try {
      for await (const step of streamChat(question, {
        conversationId: activeId,
        // The backend mints an id on the first turn; remember it so follow-ups
        // (and the sidebar) point at the same conversation.
        onMeta: (meta) => setActiveId(meta.conversation_id),
      })) {
        setExchanges((prev) => {
          const next = [...prev];
          const ex = next[index];
          if (step.type === "token") {
            // A live chunk of the model's output: grow the typewriter preview.
            next[index] = { ...ex, streaming: (ex.streaming || "") + (step.content || "") };
          } else {
            // A committed step (thinking, tool, answer) supersedes the preview.
            next[index] = { ...ex, streaming: "", steps: [...ex.steps, step] };
          }
          return next;
        });
      }
    } catch (err) {
      setExchanges((prev) => {
        const next = [...prev];
        const errStep = { type: "error", content: `Could not reach the agent: ${err.message}` };
        next[index] = { ...next[index], streaming: "", steps: [...next[index].steps, errStep] };
        return next;
      });
    } finally {
      setBusy(false);
      // A brand-new chat now exists in the database -- pull it into the sidebar.
      if (wasNew) refreshConversations();
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || busy) return;
    setInput("");
    ask(question);
  }

  async function selectConversation(id) {
    if (busy || id === activeId) return;
    try {
      const messages = await getConversation(id);
      setExchanges(toExchanges(messages));
      setActiveId(id);
    } catch (err) {
      setExchanges([{ question: "", steps: [{ type: "error", content: err.message }] }]);
    }
  }

  function newChat() {
    setActiveId(null);
    setExchanges([]);
    setInput("");
  }

  return (
    <div className="workspace">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={selectConversation}
        onNew={newChat}
        busy={busy}
      />
      <Chat
        exchanges={exchanges}
        busy={busy}
        input={input}
        onInputChange={setInput}
        onSubmit={onSubmit}
      />
    </div>
  );
}
