"""FastAPI application entry point (build step 2).

Puts the agent behind HTTP. For now that is one streaming /chat endpoint plus a
/health check, with no auth. Auth, conversation history, and image upload arrive
in later build steps; the routes are split into their own modules so those can
be added without this file growing.

Run it from the repo root so both `agent` and `backend` import as top-level
packages:

    uvicorn backend.main:app --reload
"""

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import chat

# Load GROQ_API_KEY, SERPER_API_KEY, etc. from .env before anything uses them.
load_dotenv()

app = FastAPI(title="Glasswing", version="0.1.0")

# Wide open so local curl and, later, the dev frontend can call it. Before the
# real frontend deploys we narrow allow_origins to the Vercel URL (build step 7).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)


@app.get("/health")
def health():
    return {"status": "ok"}
