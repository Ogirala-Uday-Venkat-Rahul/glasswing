"""Google sign-in: the OAuth 2.0 Authorization Code flow, by hand (build step 4).

The one place that knows how to talk to Google and how to mint a session. The
routes in routes/auth.py are thin HTTP wrappers over the functions here; this
module holds the actual protocol so the flow is readable in one file.

We deliberately do NOT use an OAuth library (authlib). The whole flow is five
plain HTTPS calls and a signed cookie, and hand-rolling it keeps every step
visible: build a URL, redirect the user, trade the code for the user's identity,
remember them. See the flow, end to end:

    1. /auth/login   -> we send the browser to Google with our public Client ID
    2. Google        -> user approves, Google sends the browser back with a code
    3. /auth/callback-> we trade {code + Client SECRET} for the user's identity
    4.               -> upsert the User row, set a signed session cookie
    5. /auth/me      -> later requests read that cookie to know who is signed in

Two secrets are in play and they live in different places on purpose:
  * the Client Secret proves *our app* to Google. It only ever leaves the server
    in the server-to-server token call (step 3) -- never to the browser.
  * SESSION_SECRET signs *our* cookie so a user cannot forge one. We never send
    it anywhere; we only sign with it and check the signature.

Optional, like db.py: if the GOOGLE_* / SESSION_SECRET env vars are unset,
is_enabled() is False and the auth routes return 503 instead of crashing, so the
app still runs (stateless, no login) before credentials are wired.
"""

import os
import secrets
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# Google's OpenID Connect endpoints. These are fixed public URLs (they come from
# Google's discovery document); hardcoding them keeps the flow dependency-free.
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"

# What we ask the user to share. openid = "log me in"; email + profile = the two
# non-sensitive scopes we registered. Space-separated, per the OAuth spec.
SCOPES = "openid email profile"

# Cookie names and lifetimes.
SESSION_COOKIE = "gw_session"
STATE_COOKIE = "gw_oauth_state"
SESSION_MAX_AGE = 60 * 60 * 24 * 7   # 7 days signed-in
STATE_MAX_AGE = 60 * 10              # the login round-trip must finish in 10 min


def _cfg() -> dict:
    """Read config from the environment on every call (lazy, like db.py).

    Read lazily rather than at import so main.py's load_dotenv() has already run.
    Cheap dict lookups, so re-reading per request is fine.
    """
    return {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv("OAUTH_REDIRECT_URI", ""),
        "session_secret": os.getenv("SESSION_SECRET", ""),
        # Where to send the browser once login succeeds -- the frontend app.
        "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:5173"),
    }


def is_enabled() -> bool:
    """True only when every piece needed to run the flow is configured."""
    c = _cfg()
    return bool(
        c["client_id"] and c["client_secret"] and c["redirect_uri"] and c["session_secret"]
    )


def frontend_url() -> str:
    return _cfg()["frontend_url"]


# --- Step 1: send the user to Google -----------------------------------------

def make_state() -> str:
    """A random, unguessable nonce that ties one login attempt together.

    We hand this to Google in step 1 and Google hands it back in step 2. By
    checking the value that comes back matches the one we sent, we prove the
    callback is the continuation of a login *we* started -- not a link an
    attacker tricked the user into clicking. This is the CSRF defence baked into
    OAuth; the `state` parameter exists for exactly this.
    """
    return secrets.token_urlsafe(24)


def login_url(state: str) -> str:
    """The Google consent URL to redirect the browser to (step 1).

    Only public values go in here -- Client ID, our redirect URI, the scopes,
    the state nonce. No secret. This URL is visible in the address bar, which is
    fine: it grants nothing on its own.
    """
    c = _cfg()
    params = {
        "client_id": c["client_id"],
        "redirect_uri": c["redirect_uri"],
        "response_type": "code",       # "give us an authorization code" (the ticket)
        "scope": SCOPES,
        "state": state,
        "prompt": "select_account",    # always let the user pick which account
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


# --- Step 3: trade the code for the user's identity --------------------------

def exchange_code(code: str) -> dict:
    """Swap the one-time code for tokens -- the server-to-server call (step 3).

    This is the hop that never touches the browser. We send the code back to
    Google *with our Client Secret* to prove we are the app the code was issued
    to. Google replies with an access token (and an id_token). Raises on any
    non-2xx so the caller can fail the login cleanly.
    """
    c = _cfg()
    resp = httpx.post(
        TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": c["client_id"],
            "client_secret": c["client_secret"],   # the proof-of-identity secret
            "redirect_uri": c["redirect_uri"],      # must match step 1 exactly
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_userinfo(access_token: str) -> dict:
    """Ask Google who the user is, using the access token from exchange_code.

    Returns Google's profile JSON: {"sub", "email", "email_verified", "name", ...}.
    `sub` is Google's stable unique id for the user; `email` is what we key on.
    """
    resp = httpx.get(
        USERINFO_ENDPOINT,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# --- Signed cookies: sessions and the state nonce ----------------------------
#
# itsdangerous signs a payload with SESSION_SECRET and can later verify it has
# not been tampered with (and, with max_age, that it is not too old). It does NOT
# encrypt -- the contents are readable -- so we only ever store a user id, never
# anything secret. Two serializers with different "salts" so a session token can
# never be replayed as a state token or vice versa.

def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_cfg()["session_secret"], salt=salt)


def sign_session(user_id: str) -> str:
    """Turn a user id into the signed string we store in the session cookie."""
    return _serializer("glasswing-session").dumps({"uid": user_id})


def read_session(token: str | None) -> str | None:
    """Recover the user id from a session cookie, or None if missing/bad/expired.

    A tampered or forged cookie fails the signature check and returns None -- the
    request is simply treated as logged-out rather than trusted.
    """
    if not token:
        return None
    try:
        data = _serializer("glasswing-session").loads(token, max_age=SESSION_MAX_AGE)
        return data.get("uid")
    except (BadSignature, SignatureExpired):
        return None


def sign_state(state: str) -> str:
    """Signed cookie value carrying the state nonce across the round-trip."""
    return _serializer("glasswing-oauth-state").dumps(state)


def read_state(token: str | None) -> str | None:
    """Recover the state nonce we set before redirecting, or None if bad/expired."""
    if not token:
        return None
    try:
        return _serializer("glasswing-oauth-state").loads(token, max_age=STATE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
