"""Cloudflare R2 object storage for uploaded images (build step 5).

Images are blobs, so they do not belong in Postgres. The database stores only
the R2 object *key* (a pointer); the bytes live here. R2 speaks the S3 API, so we
drive it with boto3 pointed at R2's endpoint.

Like db.py and trace.py, this is an OPTIONAL SEAM. With no R2 credentials set,
is_enabled() is False and the app runs without image support instead of crashing,
so a local text-only run stays zero-config. boto3 is imported lazily inside the
client for the same reason: a text-only run never loads it.
"""

import os
import uuid
from functools import lru_cache

# The four settings R2 needs. Account id builds the endpoint; the key/secret are
# an R2 API token; bucket is where uploads land.
_REQUIRED = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")

# How long a presigned view URL stays valid. Long enough for the model to fetch
# the image during a run and for the browser to show it, short enough that a
# leaked URL expires on its own.
URL_TTL_SECONDS = 3600

# Only the image types the vision model accepts, each mapped to a file extension.
_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def is_enabled() -> bool:
    """True only when every R2 setting is present."""
    return all(os.getenv(k) for k in _REQUIRED)


def is_allowed_type(content_type: str) -> bool:
    """Whether we accept (and the vision model understands) this image type."""
    return content_type in _EXT


@lru_cache(maxsize=1)
def _client():
    """The boto3 S3 client pointed at this account's R2 endpoint (built once)."""
    import boto3

    account = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",  # R2 ignores the region, but boto3 requires one
    )


def upload_image(data: bytes, content_type: str, user_id: str | None = None) -> str:
    """Store image bytes in R2 and return the object key (the pointer we persist).

    The key namespaces by user, so one prefix holds all of a person's uploads, and
    carries a random uuid so filenames never collide or leak the original name.
    """
    key = f"uploads/{user_id or 'anon'}/{uuid.uuid4().hex}{_EXT.get(content_type, '')}"
    _client().put_object(Bucket=os.environ["R2_BUCKET"], Key=key, Body=data, ContentType=content_type)
    return key


def view_url(key: str) -> str:
    """A short-lived presigned GET URL for an object key.

    R2 buckets are private, so we hand out a time-limited signed URL rather than
    make the bucket public. The vision model fetches the image through this URL,
    and the frontend uses it to redisplay a past upload. The pointer pattern
    paying off: the key is durable, the URL is disposable.
    """
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": os.environ["R2_BUCKET"], "Key": key},
        ExpiresIn=URL_TTL_SECONDS,
    )
