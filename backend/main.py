"""FastAPI application entry point (build step 2).

Puts the agent behind HTTP. For now that is one streaming /chat endpoint plus a
/health check, with no auth. Auth, conversation history, and image upload arrive
in later build steps; the routes are split into their own modules so those can
be added without this file growing.

Run it from the repo root so both `agent` and `backend` import as top-level
packages:

    uvicorn backend.main:app --reload
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .routes import auth, chat, history, upload

# Load GROQ_API_KEY, SERPER_API_KEY, DATABASE_URL, etc. from .env before anything
# uses them. db reads DATABASE_URL lazily, so it must run before init_db() below.
load_dotenv()

# Create the history tables if a database is configured. No-op (and non-fatal)
# when DATABASE_URL is unset or unreachable, so the app still serves stateless.
db.init_db()

app = FastAPI(title="Glasswing", version="0.1.0")

# The session cookie means the browser must send credentials, and a credentialed
# request may NOT use a wildcard origin -- browsers forbid allow_origins=["*"]
# together with allow_credentials=True. So we name the exact frontend origin(s).
# FRONTEND_URL lets deploy point this at the Vercel URL (build step 7).
_frontend = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend, "http://localhost:5173"],
    allow_credentials=True,   # let the browser send/receive the gw_session cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(history.router)
app.include_router(auth.router)
app.include_router(upload.router)


@app.get("/health")
def health():
    return {"status": "ok"}
