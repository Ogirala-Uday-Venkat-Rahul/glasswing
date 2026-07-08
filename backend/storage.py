"""S3-compatible object storage for uploaded images (build step 5).

Images are blobs, so they do not belong in Postgres. The database stores only
the object *key* (a pointer); the bytes live here. We talk to storage over the
S3 API with boto3, so this works with any S3-compatible provider -- Supabase
Storage, Cloudflare R2, Backblaze B2 -- by pointing S3_ENDPOINT at it. Nothing
here is provider-specific; swapping providers is four environment variables, not
a code change.

Like db.py and trace.py, this is an OPTIONAL SEAM. With no storage credentials
set, is_enabled() is False and the app runs without image support instead of
crashing, so a local text-only run stays zero-config. boto3 is imported lazily
inside the client for the same reason: a text-only run never loads it.
"""

import os
import uuid
from functools import lru_cache

# The settings storage needs. Endpoint is the provider's S3 API URL; the
# key/secret are the S3 access credentials; bucket is where uploads land. Region
# is read separately (below) because it has a sensible default.
_REQUIRED = ("S3_ENDPOINT", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "S3_BUCKET")

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
    """True only when every required storage setting is present."""
    return all(os.getenv(k) for k in _REQUIRED)


def is_allowed_type(content_type: str) -> bool:
    """Whether we accept (and the vision model understands) this image type."""
    return content_type in _EXT


@lru_cache(maxsize=1)
def _client():
    """The boto3 S3 client pointed at the configured endpoint (built once).

    We pin SigV4 ("s3v4") because Supabase (and modern S3) reject the older SigV2
    that boto3 would otherwise fall back to for a custom endpoint. Region matters
    for SigV4 signing (Supabase validates it), so it is configurable; "auto" is a
    safe default for providers that ignore it (R2). path-style addressing avoids
    provider domains that do not support the virtual-hosted bucket.subdomain form.
    """
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        region_name=os.getenv("S3_REGION", "auto"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def upload_image(data: bytes, content_type: str, user_id: str | None = None) -> str:
    """Store image bytes and return the object key (the pointer we persist).

    The key namespaces by user, so one prefix holds all of a person's uploads, and
    carries a random uuid so filenames never collide or leak the original name.
    """
    key = f"uploads/{user_id or 'anon'}/{uuid.uuid4().hex}{_EXT.get(content_type, '')}"
    _client().put_object(Bucket=os.environ["S3_BUCKET"], Key=key, Body=data, ContentType=content_type)
    return key


def delete_object(key: str) -> None:
    """Remove one stored object by key (used when a conversation is deleted).

    Best-effort cleanup so a deleted chat doesn't leave its images orphaned in the
    bucket. S3 delete is idempotent -- deleting a key that's already gone still
    succeeds -- so this is safe to call without first checking the object exists.
    """
    _client().delete_object(Bucket=os.environ["S3_BUCKET"], Key=key)


def view_url(key: str) -> str:
    """A short-lived presigned GET URL for an object key.

    Buckets are private, so we hand out a time-limited signed URL rather than make
    the bucket public. The vision model fetches the image through this URL, and the
    frontend uses it to redisplay a past upload. The pointer pattern paying off:
    the key is durable, the URL is disposable.
    """
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": os.environ["S3_BUCKET"], "Key": key},
        ExpiresIn=URL_TTL_SECONDS,
    )
