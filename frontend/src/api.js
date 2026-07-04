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

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function parseFrame(frame) {
  // One SSE event block -> the JSON object on its data: line, or null.
  let data = null;
  for (const line of frame.split("\n")) {
    if (line.startsWith("data:")) {
      data = line.slice(5).trim();
    }
  }
  if (data === null) return null;
  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}

export async function* streamChat(message, apiBase = API_BASE) {
  const res = await fetch(`${apiBase}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
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
      const step = parseFrame(frame);
      if (step) yield step;
    }
  }
}
