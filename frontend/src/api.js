// Talks to the backend's streaming /chat endpoint.
//
// The browser has a built-in tool for server-sent events (EventSource), but it
// can only make GET requests, and our /chat is a POST that carries the question
// in a JSON body. So we use fetch() and read the response body as a stream
// ourselves, parsing the small SSE text format by hand. It is only a few rules:
//
//   - events are separated by a blank line
//   - within an event, a line "data: {...}" carries the payload
//   - a line "event: step" names the event type (we only send "step")
//
// streamChat is an async generator: `for await (const step of streamChat(msg))`
// gives you each Step the moment it arrives, exactly as the backend emits it.
//
// The backend sends two kinds of event. The very first is "meta", carrying the
// conversation_id so the client can send it back on the next turn and continue
// the same thread (multi-turn memory). The rest are "step" events. We yield only
// the steps and hand the meta payload to an onMeta callback, so callers keep the
// simple `for await (const step of ...)` loop without the meta frame leaking in.

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// --- Auth -------------------------------------------------------------------
//
// The session lives in an httpOnly cookie the JS can't read, so we never handle
// a token here. Instead every auth call sends `credentials: "include"`, which
// tells the browser to attach the gw_session cookie; the server reads it and
// tells us who (if anyone) is signed in.

export async function getMe(apiBase = API_BASE) {
  // "Who am I?" Returns { authenticated: false } or { authenticated: true, user }.
  const res = await fetch(`${apiBase}/auth/me`, { credentials: "include" });
  if (!res.ok) return { authenticated: false };
  return res.json();
}

export function login(apiBase = API_BASE) {
  // A full-page navigation, not fetch: the login is a chain of redirects
  // (our backend -> Google -> back) that the browser itself must follow.
  window.location.href = `${apiBase}/auth/login`;
}

export async function logout(apiBase = API_BASE) {
  await fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" });
}

// --- Conversation history ---------------------------------------------------

export async function listConversations(apiBase = API_BASE) {
  // The signed-in user's past chats for the recents sidebar. [] when signed out.
  const res = await fetch(`${apiBase}/conversations`, { credentials: "include" });
  if (!res.ok) return [];
  const data = await res.json();
  return data.conversations || [];
}

export async function getConversation(id, apiBase = API_BASE) {
  // The saved turns of one chat: [{ role, content, created_at }], oldest first.
  const res = await fetch(`${apiBase}/history/${id}`, { credentials: "include" });
  if (!res.ok) throw new Error(`Could not load conversation (${res.status})`);
  const data = await res.json();
  return data.messages || [];
}

function parseFrame(frame) {
  // One SSE event block -> { event, data }, or null if it has no data line.
  // Per the SSE spec an event with no "event:" line defaults to "message"; our
  // backend always names its events, but we default to "step" to be safe.
  let event = "step";
  let data = null;
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      data = line.slice(5).trim();
    }
  }
  if (data === null) return null;
  try {
    return { event, data: JSON.parse(data) };
  } catch {
    return null;
  }
}

export async function* streamChat(message, { conversationId = null, onMeta } = {}, apiBase = API_BASE) {
  const res = await fetch(`${apiBase}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // Send the gw_session cookie so the backend knows who is asking and can own
    // the conversation. Without this the browser withholds the cookie on POST.
    credentials: "include",
    // conversation_id is null on the first turn (the server mints one) and the
    // saved id on later turns (the server loads that thread's history).
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (!res.ok || !res.body) {
    throw new Error(`Request failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    // The server ends lines with "\r\n" (the SSE standard), so events are
    // separated by "\r\n\r\n". Strip the carriage returns as chunks arrive so
    // the blank-line split below can just look for "\n\n".
    buffer += decoder.decode(value, { stream: true }).replace(/\r/g, "");

    // A frame is complete once we see the blank line that ends it. There may be
    // several ready in the buffer at once, so drain them all before reading more.
    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const parsed = parseFrame(frame);
      if (!parsed) continue;
      if (parsed.event === "meta") {
        if (onMeta) onMeta(parsed.data);
        continue;
      }
      yield parsed.data;
    }
  }
}
