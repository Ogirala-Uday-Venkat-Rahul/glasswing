import { useState, useEffect, useRef } from "react";
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

  // PWA install prompt handler
  const [installPrompt, setInstallPrompt] = useState(null);
  const [isInstalled, setIsInstalled] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone) {
      setIsInstalled(true);
      return;
    }

    function onBeforeInstallPrompt(e) {
      e.preventDefault();
      setInstallPrompt(e);
    }
    function onAppInstalled() {
      setIsInstalled(true);
      setInstallPrompt(null);
    }

    window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
    window.addEventListener("appinstalled", onAppInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstallPrompt);
      window.removeEventListener("appinstalled", onAppInstalled);
    };
  }, []);

  async function handleInstallApp() {
    if (installPrompt) {
      installPrompt.prompt();
      const { outcome } = await installPrompt.userChoice;
      if (outcome === "accepted") {
        setInstallPrompt(null);
        setIsInstalled(true);
      }
    } else {
      // Friendly fallback instructions for iOS Safari or browsers without beforeinstallprompt
      alert(
        "To install Glasswing as an app:\n\n" +
        "• On Android / Desktop Chrome: Tap the browser menu (⋮) and select 'Install app' or 'Add to Home screen'.\n\n" +
        "• On iPhone / iPad (Safari): Tap the Share button at the bottom (box with arrow) and tap 'Add to Home Screen'."
      );
    }
  }

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
          {!isInstalled && (
            <button
              type="button"
              className="install-btn"
              onClick={handleInstallApp}
              title="Install Glasswing as an app"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              <span>Install</span>
            </button>
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
            <UserMenu user={me.user} onSignOut={signOut} />
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

function UserMenu({ user, onSignOut }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    function handleKeyDown(e) {
      if (e.key === "Escape") setOpen(false);
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <div className="user-menu-wrap" ref={menuRef}>
      <button
        type="button"
        className={`user-trigger ${open ? "open" : ""}`}
        onClick={() => setOpen((prev) => !prev)}
        aria-label="User account menu"
        aria-expanded={open}
      >
        <span className="avatar" aria-hidden="true">
          {user.email[0].toUpperCase()}
        </span>
        <span className="user-trigger-email">{user.email}</span>
        <svg
          className={`user-trigger-chevron ${open ? "open" : ""}`}
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="user-dropdown">
          <div className="user-dropdown-header">
            <span className="user-dropdown-avatar">{user.email[0].toUpperCase()}</span>
            <div className="user-dropdown-info">
              <span className="user-dropdown-label">Signed in as</span>
              <span className="user-dropdown-email" title={user.email}>{user.email}</span>
            </div>
          </div>
          <div className="user-dropdown-divider" />
          <button
            type="button"
            className="user-dropdown-signout"
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
