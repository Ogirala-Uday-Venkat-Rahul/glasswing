import { login } from "../api.js";

// The signed-out screen. One button, which hands off to the backend's
// /auth/login (a full-page navigation, since the login is a redirect chain the
// browser must follow). When Google sends the user back, the backend redirects
// to "/?auth=ok" | "denied" | "error"; App reads that and passes the message
// here so a cancelled or failed attempt says something instead of silently
// returning to this screen.

export default function Login({ notice }) {
  return (
    <div className="login">
      <div className="login-card">
        <h2>Sign in to Glasswing</h2>
        <p className="login-sub">
          Your conversations are saved to your account, so you can pick up where
          you left off.
        </p>

        {notice && <div className="login-notice">{notice}</div>}

        <button className="google-btn" onClick={() => login()}>
          <GoogleMark />
          Sign in with Google
        </button>
      </div>
    </div>
  );
}

// Google's wordmark colours, inline so there's no external asset to load.
function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.02-3.7H.96v2.34A9 9 0 0 0 9 18z" />
      <path fill="#FBBC05" d="M3.98 10.72a5.4 5.4 0 0 1 0-3.44V4.94H.96a9 9 0 0 0 0 8.12l3.02-2.34z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.47.9 11.43 0 9 0A9 9 0 0 0 .96 4.94l3.02 2.34C4.68 5.16 6.66 3.58 9 3.58z" />
    </svg>
  );
}
