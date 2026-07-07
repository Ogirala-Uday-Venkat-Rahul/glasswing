"""Image upload endpoint (build step 5).

The flow is two-step by design: the browser uploads an image here FIRST and gets
back an opaque object key, then sends that key alongside the next chat message.
Keeping upload separate from /chat means the (potentially large, slow) file
transfer isn't tangled up in the SSE stream, and the key is a small, cheap thing
to carry on the message.

The bytes go to Cloudflare R2 (see backend/storage.py); nothing image-related
touches Postgres except the returned key, which the chat turn stores as a pointer.
"""

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from .. import auth, storage

router = APIRouter()

# A ceiling so one request can't stream an unbounded file into memory. The vision
# model caps images anyway; 10 MB comfortably covers a photo without inviting abuse.
MAX_IMAGE_BYTES = 10 * 1024 * 1024


@router.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    """Store one uploaded image in R2 and return its object key.

    503 if image storage isn't configured (no R2 creds) — the frontend hides the
    attach button in that case, but we guard the endpoint too. 415 for a file type
    the vision model can't read, 413 for one over the size cap.
    """
    if not storage.is_enabled():
        raise HTTPException(status_code=503, detail="Image upload is not configured.")

    if not storage.is_allowed_type(file.content_type or ""):
        raise HTTPException(status_code=415, detail="Unsupported image type.")

    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image is too large (10 MB max).")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")

    # Namespace the upload under the signed-in user when there is one, so a
    # person's images live under one prefix. Anonymous uploads still work.
    user_id = auth.read_session(request.cookies.get(auth.SESSION_COOKIE))
    key = storage.upload_image(data, file.content_type, user_id=user_id)
    return {"image_key": key}
