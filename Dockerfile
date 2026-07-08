# Container image for the FastAPI backend, deployed to Render.
# The image holds only what the server needs at runtime: the two Python packages
# (agent/ and backend/) and their dependencies. The frontend builds and ships
# separately on Vercel, so it is not copied in (see .dockerignore).

FROM python:3.12-slim

# Don't buffer stdout/stderr, and don't write .pyc files: logs show up in Cloud
# Run immediately and the image stays a little smaller.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install deps first, as their own layer, so code changes don't re-run pip.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The app imports `agent` and `backend` as top-level packages, so both dirs sit
# at the working directory root (same as running uvicorn from the repo root).
COPY agent/ ./agent/
COPY backend/ ./backend/

# Render sends traffic to the port named in $PORT. Bind to it and to 0.0.0.0 so
# the container is reachable from outside. Shell form so $PORT is expanded at
# runtime; the 8080 fallback lets the image also run on hosts that don't set it.
CMD exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}
