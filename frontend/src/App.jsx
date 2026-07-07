import { useState, useEffect } from "react";
import Workspace from "./components/Workspace.jsx";
import Login from "./components/Login.jsx";
import { getMe, logout } from "./api.js";

// The app is gated on being signed in. On load we ask the backend "who am I?"
// (getMe reads the session cookie); until that returns we show nothing decisive,
// then we branch: signed in -> the chat, signed out -> the login screen.

// The backend sends the user back to "/?auth=ok|denied|error" after a login
// attempt. We translate the failure cases into a human message for the login
// screen, then strip the query string so a refresh doesn't repeat it.
const AUTH_NOTICES = {
  denied: "Sign-in was cancelled. Give it another try when you're ready.",
  error: "Something went wrong signing in. Please try again.",
};

function readAuthNotice() {
  const status = new URLSearchParams(window.location.search).get("auth");
  if (status) {
    window.history.replaceState({}, "", window.location.pathname);
  }
  return AUTH_NOTICES[status] || "";
}

export default function App() {
  // null = still checking; otherwise the {authenticated, user} shape from getMe.
  const [me, setMe] = useState(null);
  const [notice] = useState(readAuthNotice);

  useEffect(() => {
    getMe().then(setMe);
  }, []);

  async function signOut() {
    await logout();
    setMe({ authenticated: false });
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Glasswing</h1>
        <p className="tagline">An agent you can see think.</p>
      </header>

      {me === null ? (
        <div className="empty">Loading…</div>
      ) : me.authenticated ? (
        <>
          <div className="userbar">
            <span className="avatar" aria-hidden="true">
              {me.user.email[0].toUpperCase()}
            </span>
            <span className="userbar-email">{me.user.email}</span>
            <button className="signout" onClick={signOut}>
              Sign out
            </button>
          </div>
          <Workspace />
        </>
      ) : (
        <Login notice={notice} />
      )}
    </div>
  );
}
