import { useState, useEffect } from "react";
import Sidebar from "./Sidebar.jsx";
import Chat from "./Chat.jsx";
import { streamChat, listConversations, getConversation, uploadImage } from "../api.js";

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
      // image_url is a presigned link the history endpoint adds for turns that
      // had a picture attached, so a reloaded chat shows the image again.
      out.push({ question: m.content, image: m.image_url || null, steps: [] });
    } else {
      if (out.length === 0) out.push({ question: "", steps: [] });
      out[out.length - 1].steps.push({ type: "final_answer", content: m.content });
    }
  }
  return out;
}

export default function Workspace({ onAgentState }) {
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null); // null = a fresh, unsaved chat
  const [exchanges, setExchanges] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  // An image picked but not yet sent: { file, url } where url is a local preview.
  const [pending, setPending] = useState(null);

  function pickImage(file) {
    if (!file) return;
    setPending({ file, url: URL.createObjectURL(file) });
  }

  function clearImage() {
    if (pending) URL.revokeObjectURL(pending.url);
    setPending(null);
  }

  // Load the recents list once on mount.
  useEffect(() => {
    refreshConversations();
  }, []);

  async function refreshConversations() {
    setConversations(await listConversations());
  }

  // Tell the header mascot the agent just finished: a brief "done" pop, then calm.
  function settleAgent() {
    onAgentState?.("done");
    setTimeout(() => onAgentState?.("idle"), 1400);
  }

  async function ask(question, imageFile) {
    setBusy(true);
    onAgentState?.("working");
    const index = exchanges.length; // where this turn's exchange will live
    const wasNew = activeId === null;
    // A fresh preview URL owned by this exchange (the composer's own preview is
    // released on submit, so we don't share it).
    const preview = imageFile ? URL.createObjectURL(imageFile) : null;
    setExchanges((prev) => [...prev, { question, image: preview, steps: [], streaming: "" }]);

    // If a picture is attached, upload it first to get its storage key. A failed
    // upload stops here with an error step rather than sending a broken turn.
    let imageKey = null;
    if (imageFile) {
      try {
        imageKey = await uploadImage(imageFile);
      } catch (err) {
        setExchanges((prev) => {
          const next = [...prev];
          const errStep = { type: "error", content: `Could not upload the image: ${err.message}` };
          next[index] = { ...next[index], streaming: "", steps: [errStep] };
          return next;
        });
        setBusy(false);
        onAgentState?.("idle");
        return;
      }
    }

    try {
      for await (const step of streamChat(question, {
        conversationId: activeId,
        imageKey,
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
      settleAgent();
      // A brand-new chat now exists in the database -- pull it into the sidebar.
      if (wasNew) refreshConversations();
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    // An image on its own is a valid turn — default the wording so the model has
    // something to answer.
    const question = input.trim() || (pending ? "What's in this image?" : "");
    if (!question || busy) return;
    const imageFile = pending?.file || null;
    if (pending) URL.revokeObjectURL(pending.url); // ask() makes its own preview
    setInput("");
    setPending(null);
    ask(question, imageFile);
  }

  // An example prompt was clicked on the empty screen: ask it straight away.
  function askExample(question) {
    if (busy) return;
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
        onExample={askExample}
        pendingImage={pending?.url || null}
        onPickImage={pickImage}
        onClearImage={clearImage}
      />
    </div>
  );
}
