"""Google sign-in endpoints (build step 4).

Four small routes that drive the flow in auth.py:

    GET  /auth/login    -> redirect the browser to Google's consent screen
    GET  /auth/callback -> Google returns here; finish login, set the cookie
    GET  /auth/me       -> "who am I?" -- reads the session cookie
    POST /auth/logout   -> clear the session cookie

Login needs a database (a User row to upsert) *and* configured Google creds, so
both /auth/login and /auth/callback 503 if either is missing. /auth/me and
/auth/logout only touch the cookie, so they work regardless.

Cookie flags worth knowing (set the same way everywhere):
  * httponly=True  -- JavaScript cannot read the cookie, so an XSS bug can't
                      steal the session. Only the server ever sees it.
  * samesite="lax" -- the cookie still rides along on the top-level redirect back
                      from Google (a GET navigation), but not on random
                      cross-site POSTs. The right balance for a login cookie.
  * secure         -- HTTPS-only. True in production; on http://localhost it must
                      be False or the browser silently drops the cookie. We infer
                      it from whether our redirect URI is https.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .. import auth, store
from ..db import is_enabled as db_enabled
from ..db import new_session

router = APIRouter(prefix="/auth")


def _secure_cookies() -> bool:
    # On localhost (http) cookies must not be Secure or the browser drops them;
    # once OAUTH_REDIRECT_URI is an https URL (deploy), Secure turns on by itself.
    return auth._cfg()["redirect_uri"].startswith("https://")


@router.get("/login")
def login():
    """Step 1: bounce the browser to Google, remembering a CSRF state nonce."""
    if not auth.is_enabled() or not db_enabled():
        raise HTTPException(status_code=503, detail="Sign-in is not configured.")

    state = auth.make_state()
    response = RedirectResponse(auth.login_url(state), status_code=302)
    # Stash the state in a short-lived signed cookie so we can compare it against
    # what Google echoes back in the callback. Signed so it can't be swapped.
    response.set_cookie(
        auth.STATE_COOKIE,
        auth.sign_state(state),
        max_age=auth.STATE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_secure_cookies(),
        path="/",
    )
    return response


@router.get("/callback")
def callback(request: Request, code: str | None = None, state: str | None = None):
    """Steps 2-4: Google returns here; verify, exchange, upsert, set session."""
    if not auth.is_enabled() or not db_enabled():
        raise HTTPException(status_code=503, detail="Sign-in is not configured.")

    # A failed login (user hit "Cancel", or an error) comes back with no code.
    # Send them back to the app rather than showing a bare error page.
    if not code:
        return RedirectResponse(f"{auth.frontend_url()}/?auth=denied", status_code=302)

    # CSRF check: the state Google echoed must match the one we signed into the
    # cookie before redirecting. A mismatch means this callback isn't ours.
    expected = auth.read_state(request.cookies.get(auth.STATE_COOKIE))
    if not state or state != expected:
        raise HTTPException(status_code=400, detail="Invalid or expired login state.")

    # The two network calls that turn the code into an identity.
    try:
        tokens = auth.exchange_code(code)
        profile = auth.fetch_userinfo(tokens["access_token"])
    except Exception as exc:  # noqa: BLE001 - any failure here is a failed login
        print(f"[auth] token exchange failed: {exc}")
        return RedirectResponse(f"{auth.frontend_url()}/?auth=error", status_code=302)

    email = profile.get("email")
    if not email:
        return RedirectResponse(f"{auth.frontend_url()}/?auth=error", status_code=302)

    # Upsert the user and mint the session.
    db = new_session()
    try:
        user = store.get_or_create_user(db, email)
        db.commit()
        user_id = user.id
    finally:
        db.close()

    # Back to the app, now carrying a signed session cookie. The state cookie has
    # done its job -- delete it.
    response = RedirectResponse(f"{auth.frontend_url()}/?auth=ok", status_code=302)
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.sign_session(user_id),
        max_age=auth.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_secure_cookies(),
        path="/",
    )
    response.delete_cookie(auth.STATE_COOKIE, path="/")
    return response


@router.get("/me")
def me(request: Request):
    """Who is signed in? Reads the session cookie and looks the user up.

    Always 200 with an {authenticated: bool} shape so the frontend can branch
    without treating "logged out" as an error.
    """
    user_id = auth.read_session(request.cookies.get(auth.SESSION_COOKIE))
    if not user_id or not db_enabled():
        return {"authenticated": False}

    db = new_session()
    try:
        user = db.get(store.User, user_id)
        if user is None:
            return {"authenticated": False}
        return {"authenticated": True, "user": {"id": user.id, "email": user.email}}
    finally:
        db.close()


@router.post("/logout")
def logout():
    """Forget the session by clearing the cookie. Nothing server-side to undo."""
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return response
