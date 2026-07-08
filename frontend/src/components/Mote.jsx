// Mote — the Glasswing mascot: a winged spark that reacts to the agent.
//
// It has three states, driven by the `state` prop:
//   - "idle"    : still, a faint hover (nothing is happening)
//   - "working" : fast wing-flutter + glow pulse (the agent is thinking / using tools)
//   - "done"    : a quick pop, then back to calm (an answer just landed)
//
// The visuals are pure SVG + CSS (see .mote rules in styles.css) so there's no
// asset to load and it recolours with the theme accent. The wing gradient stops
// read the --accent / --accent-ink CSS variables via the .s-ac / .s-hi classes.

export default function Mote({ state = "idle", size = 38 }) {
  const cls =
    "mote" + (state === "working" ? " is-working" : state === "done" ? " is-done" : "");
  return (
    <svg
      className={cls}
      style={{ width: size, height: size }}
      viewBox="0 0 100 100"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="mote-wing" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" className="s-hi" />
          <stop offset="1" className="s-ac" />
        </linearGradient>
        <radialGradient id="mote-core" cx="50%" cy="42%" r="60%">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" className="s-ac" />
        </radialGradient>
      </defs>
      <g className="flo">
        <path
          className="wing wl"
          d="M50 52 C30 30 8 34 6 54 C24 51 40 51 50 52Z"
          fill="url(#mote-wing)"
          fillOpacity="0.28"
          stroke="url(#mote-wing)"
          strokeWidth="2"
        />
        <path
          className="wing wr"
          d="M50 52 C70 30 92 34 94 54 C76 51 60 51 50 52Z"
          fill="url(#mote-wing)"
          fillOpacity="0.28"
          stroke="url(#mote-wing)"
          strokeWidth="2"
        />
        <circle className="core" cx="50" cy="53" r="11" fill="url(#mote-core)" />
        <circle
          className="core"
          cx="50"
          cy="53"
          r="11"
          fill="none"
          stroke="#ffffff"
          strokeOpacity="0.55"
          strokeWidth="1"
        />
      </g>
    </svg>
  );
}
