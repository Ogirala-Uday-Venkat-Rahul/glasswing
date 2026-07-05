# Glasswing

An AI agent you can watch think. Glasswing takes a question, decides which tools it
needs, calls them, and streams every step to the browser in real time: its reasoning,
each tool call, each result, and the final answer. The name comes from the glasswing
butterfly, whose wings are transparent. The idea here is the same: nothing about the
agent's decision process is hidden.

## What it does

- Runs a hand-rolled tool-calling loop over a Groq model. The model decides when to
  call a tool and when it has enough to answer.
- Ships five tools: web search (Serper / Google results), URL fetch and extract (httpx + trafilatura),
  a calculator, a current date/time lookup, and a unit and temperature converter. The
  calculator is deliberate: it shows the agent delegating arithmetic instead of
  hallucinating numbers.
- Checks its own answers: a deterministic grounding pass flags any figure that doesn't
  appear in the retrieved evidence, so the agent doesn't state numbers it can't support.
- Streams each step to the frontend over SSE, rendered as a live timeline.
- Remembers the conversation. Each turn is saved to Postgres and replayed on the next
  question, so follow-ups work; a stored chat can be reloaded by its id.
- Accepts image input. You can ask questions about an uploaded picture.
- Signs you in with Google and keeps per-user conversation history.

## Architecture

```
frontend (Vite + React, Vercel)
   |  SSE
backend (FastAPI, Cloud Run)
   |            |               |
 agent loop   Neon Postgres    Cloudflare R2
 (Groq)       text records     image blobs
```

- **Text** (users, conversations, messages) lives in Neon Postgres. A real schema
  gives transactions, queries, and sorting.
- **Images** live in Cloudflare R2. The database stores only the R2 object key, never
  the bytes. Right tool for each job.
- **Tracing** is optional. `agent/trace.py` is a no-op unless a Langfuse key is
  present, so the core loop stays clean and observability is a seam you can turn on.

## Stack

| Layer        | Choice                                             |
|--------------|----------------------------------------------------|
| Model        | Groq `qwen/qwen3.6-27b` (text, vision, tools, JSON) |
| Fallback     | Groq `llama-3.3-70b-versatile`                     |
| Agent loop   | Hand-rolled, Groq native tool-calling             |
| Backend      | FastAPI, SSE                                       |
| Frontend     | Vite + React                                       |
| Database     | Neon Postgres                                      |
| Image store  | Cloudflare R2                                      |
| Auth         | Google OAuth                                       |
| Tracing      | Langfuse (optional)                                |
| Hosting      | Cloud Run (backend) + Vercel (frontend)           |

## Build order

Each layer is testable before the next one starts.

1. `agent/` core: LLM client, three tools, the loop, the trace seam. Unit tested and
   runnable from the CLI. No web or auth yet.
2. FastAPI `/chat` SSE endpoint, no auth. Verify with curl.
3. Neon plus conversation history.
4. Google OAuth.
5. R2 image persistence (object-key pointer pattern).
6. Custom frontend: chat, step timeline, image upload, login.
7. Deploy to Cloud Run and Vercel, wire CORS and redirect URIs.
8. Documentation.

## Local development

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
cp .env.example .env   # then fill in keys
```

Frontend setup lands with build step 6.

## Repository layout

```
agent/
  llm.py         model client and the seam for swapping providers
  loop.py        the tool-calling loop
  schemas.py     request/response and step types
  grounding.py   deterministic check that answers cite their evidence
  trace.py       no-op tracing unless Langfuse is configured
  tools/
    __init__.py  registry and tool schemas
    web_search.py
    fetch_url.py
    calculator.py
    current_datetime.py
    convert.py
backend/
  main.py
  auth.py        Google OAuth
  deps.py        current_user dependency
  routes/
    chat.py      SSE endpoint
    history.py   read a stored conversation
  db.py          Neon engine and session factory (optional seam)
  models.py      User / Conversation / Message
  store.py       conversation history queries
  storage.py     R2 upload and presigned URLs
frontend/
  src/
    api.js       consumes the SSE stream
    components/
      Login.jsx
      Chat.jsx
      StepTimeline.jsx
tests/
```
