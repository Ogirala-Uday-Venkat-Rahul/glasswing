import { useState, useEffect, useRef } from "react";
import Sidebar from "./Sidebar.jsx";
import Chat from "./Chat.jsx";
import {
  streamChat,
  listConversations,
  getConversation,
  uploadImage,
  deleteConversation as apiDeleteConversation,
} from "../api.js";

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
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const abortRef = useRef(null);
  // The active image attachment, or null. It stays attached across follow-up
  // turns (a "sticky" image), so you can keep asking about the same picture --
  // the model sees it again each turn -- until you remove it or pick another.
  // Shape: { file, url, key } where url is a local preview and key is the storage
  // key from the first upload (null until it has been uploaded once).
  const [attachment, setAttachment] = useState(null);

  function pickImage(file) {
    if (!file) return;
    setAttachment((prev) => {
      if (prev) URL.revokeObjectURL(prev.url); // release the one we're replacing
      return { file, url: URL.createObjectURL(file), key: null };
    });
  }

  function clearImage() {
    setAttachment((prev) => {
      if (prev) URL.revokeObjectURL(prev.url);
      return null;
    });
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

  async function ask(question) {
    setBusy(true);
    onAgentState?.("working");
    const index = exchanges.length; // where this turn's exchange will live
    const wasNew = activeId === null;
    // Snapshot the attachment for this turn: the user can clear or replace it
    // while the request is in flight, so we work from this fixed reference.
    const att = attachment;
    // A fresh preview URL owned by this exchange, so the transcript keeps showing
    // the image even after the sticky attachment is later cleared or replaced
    // (which revokes its own url). A sticky image rides along on every turn it's
    // attached, and each of those turns shows it -- honest, since the model saw it.
    const preview = att ? URL.createObjectURL(att.file) : null;
    setExchanges((prev) => [...prev, { question, image: preview, steps: [], streaming: "" }]);

    // Make sure the attachment is uploaded and we have its storage key. We upload
    // only once: a sticky image reuses the key it got the first time, so later
    // turns don't re-upload the same bytes. A failed upload stops here with an
    // error step rather than sending a broken turn.
    let imageKey = att?.key || null;
    if (att && !imageKey) {
      try {
        imageKey = await uploadImage(att.file);
        // Cache the key on the attachment so follow-up turns reuse it -- but only
        // if the user hasn't swapped or cleared it while the upload was running.
        setAttachment((cur) => (cur === att ? { ...cur, key: imageKey } : cur));
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

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const step of streamChat(question, {
        conversationId: activeId,
        imageKey,
        signal: controller.signal,
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
      const isAbort = err.name === "AbortError" || controller.signal.aborted;
      setExchanges((prev) => {
        const next = [...prev];
        const stepContent = isAbort ? "Generation stopped by user." : `Could not reach the agent: ${err.message}`;
        const errStep = { type: isAbort ? "thinking" : "error", content: stepContent };
        next[index] = { ...next[index], streaming: "", steps: [...next[index].steps, errStep] };
        return next;
      });
    } finally {
      abortRef.current = null;
      setBusy(false);
      settleAgent();
      // A brand-new chat now exists in the database -- pull it into the sidebar.
      if (wasNew) refreshConversations();
    }
  }

  function handleStop() {
    if (abortRef.current) {
      abortRef.current.abort();
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    // An image on its own is a valid turn — default the wording so the model has
    // something to answer.
    const question = input.trim() || (attachment ? "What's in this image?" : "");
    if (!question || busy) return;
    setInput("");
    // The attachment is deliberately NOT cleared here: it stays attached so the
    // next message keeps referring to the same image. Remove it with the × when done.
    ask(question);
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

  async function deleteConversation(id) {
    const wasActive = id === activeId;
    try {
      await apiDeleteConversation(id);
      if (wasActive) newChat(); // the open chat is gone -> clear the pane
    } catch (err) {
      // Non-fatal: the refresh below re-reads the truth (a failed delete simply
      // leaves the chat in the list).
      console.error("Could not delete conversation:", err);
    } finally {
      refreshConversations();
    }
  }

  return (
    <div className="workspace">
      {/* Mobile top navigation bar */}
      <div className="mobile-bar">
        <button
          type="button"
          className="mobile-bar-btn"
          onClick={() => setSidebarOpen(true)}
          aria-label="Open chat history"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
          <span>Chats {conversations.length > 0 ? `(${conversations.length})` : ""}</span>
        </button>

        <button
          type="button"
          className="mobile-bar-btn new-chat"
          onClick={() => {
            newChat();
            setSidebarOpen(false);
          }}
          disabled={busy}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>New chat</span>
        </button>
      </div>

      {sidebarOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={(id) => {
          selectConversation(id);
          setSidebarOpen(false);
        }}
        onNew={() => {
          newChat();
          setSidebarOpen(false);
        }}
        onDelete={deleteConversation}
        onAskHeadline={(q) => {
          askExample(q);
          setSidebarOpen(false);
        }}
        busy={busy}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <Chat
        exchanges={exchanges}
        busy={busy}
        input={input}
        onInputChange={setInput}
        onSubmit={onSubmit}
        onStop={handleStop}
        onExample={askExample}
        attachedImage={attachment?.url || null}
        onPickImage={pickImage}
        onClearImage={clearImage}
      />
    </div>
  );
}
