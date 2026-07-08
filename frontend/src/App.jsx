import { useState, useEffect } from "react";
import Workspace from "./components/Workspace.jsx";
import Login from "./components/Login.jsx";
import Mote from "./components/Mote.jsx";
import { getMe, logout } from "./api.js";

// The app is gated on being signed in. On load we ask the backend "who am I?"
// (getMe reads the session cookie); until that returns we show a boot screen,
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
  // A slow first load usually means the backend is cold-starting (free tier
  // sleeps when idle). After a few seconds we say so instead of a bare spinner.
  const [slowBoot, setSlowBoot] = useState(false);
  // Drives the header mascot: "idle" | "working" | "done".
  const [agentState, setAgentState] = useState("idle");
  // Theme: dark by default; persisted so a return visit keeps the choice.
  const [theme, setTheme] = useState(() => localStorage.getItem("gw-theme") || "dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("gw-theme", theme);
  }, [theme]);

  // Ask who we are, and survive a cold/unreachable backend: retry with backoff
  // instead of hanging on the spinner forever.
  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    const slowTimer = setTimeout(() => !cancelled && setSlowBoot(true), 4000);

    async function load() {
      try {
        const who = await getMe();
        if (cancelled) return;
        clearTimeout(slowTimer);
        setMe(who);
      } catch {
        // Connection refused (backend down/waking) -- back off and try again.
        attempts += 1;
        if (!cancelled) setTimeout(load, Math.min(1500 * attempts, 6000));
      }
    }
    load();
    return () => {
      cancelled = true;
      clearTimeout(slowTimer);
    };
  }, []);

  async function signOut() {
    await logout();
    setMe({ authenticated: false });
  }

  function toggleTheme() {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <Mote state={me === null ? "working" : agentState} />
          <div className="brand-text">
            <h1>Glass<span>wing</span></h1>
            <p className="tagline">An agent you can see think.</p>
          </div>
        </div>
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label="Toggle light and dark theme"
          title="Toggle theme"
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </header>

      {me === null ? (
        <div className="booting">
          <Mote state="working" size={44} />
          <span>
            {slowBoot
              ? "Waking up the server… the first load can take a few seconds."
              : "Loading…"}
          </span>
        </div>
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
          <Workspace onAgentState={setAgentState} />
        </>
      ) : (
        <Login notice={notice} />
      )}
    </div>
  );
}
