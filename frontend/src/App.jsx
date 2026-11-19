import { useState, useEffect } from "react";
import Workspace from "./components/Workspace.jsx";
import Login from "./components/Login.jsx";
import Mote from "./components/Mote.jsx";
import { getMe, logout, checkHealth } from "./api.js";

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
  // Backend availability probe for Render free-tier cold starts.
  const [backendOnline, setBackendOnline] = useState(null);
  // Theme: dark by default; persisted so a return visit keeps the choice.
  const [theme, setTheme] = useState(() => localStorage.getItem("gw-theme") || "dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("gw-theme", theme);
  }, [theme]);

  // Probe backend health to detect cold starts
  useEffect(() => {
    let active = true;
    async function probe() {
      const ok = await checkHealth();
      if (active) setBackendOnline(ok);
      // If offline/waking, retry in 5s until it wakes up
      if (!ok && active) {
        setTimeout(probe, 5000);
      }
    }
    probe();
    return () => { active = false; };
  }, []);

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
        setBackendOnline(true);
      } catch {
        // Connection refused (backend down/waking) -- back off and try again.
        setBackendOnline(false);
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
        <div className="header-right">
          {backendOnline !== null && (
            <div
              className={`status-pill ${backendOnline ? "online" : "waking"}`}
              title={
                backendOnline
                  ? "Render backend is awake and responsive"
                  : "Render backend is currently cold-starting (~50s on free tier)"
              }
            >
              <span className="status-dot" />
              <span>{backendOnline ? "Backend: Online" : "Backend: Waking (~50s)"}</span>
            </div>
          )}
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label="Toggle light and dark theme"
            title="Toggle theme"
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
          {me?.authenticated && (
            <div className="header-user">
              <span className="avatar" title={me.user.email} aria-hidden="true">
                {me.user.email[0].toUpperCase()}
              </span>
              <button className="signout" onClick={signOut} title="Sign out">
                Sign out
              </button>
            </div>
          )}
        </div>
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
        <Workspace onAgentState={setAgentState} />
      ) : (
        <Login notice={notice} />
      )}
    </div>
  );
}
