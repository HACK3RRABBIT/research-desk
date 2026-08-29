import React, { useEffect, useState, useCallback } from "react";
import { api } from "./api.js";
import { TrustBars, TierDonut, ThemeBars } from "./charts.jsx";
import { SettingsPage, EngineForm } from "./Settings.jsx";

const PAGES = [
  { id: "brief", label: "Brief", ico: "brief" },
  { id: "dash", label: "Dashboard", ico: "dash" },
  { id: "sources", label: "Sources", ico: "sources" },
  { id: "settings", label: "Settings", ico: "settings" },
];

const FEEDBACK_LABELS = [
  ["useful", "Useful"], ["not_useful", "Not useful"],
  ["rumor", "Rumor"], ["too_local", "Too local"],
  ["too_political", "Too political"], ["want_more", "Want more"],
];

const ICONS = {
  brief: (p) => (<svg viewBox="0 0 24 24" {...p}><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 9h8M8 12h8M8 15h5"/></svg>),
  dash: (p) => (<svg viewBox="0 0 24 24" {...p}><rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/></svg>),
  sources: (p) => (<svg viewBox="0 0 24 24" {...p}><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2.4"/><path d="M12 4v8"/></svg>),
  settings: (p) => (<svg viewBox="0 0 24 24" {...p}><path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="11" cy="18" r="2"/></svg>),
  play: (p) => (<svg viewBox="0 0 24 24" {...p}><path d="M6 4l14 8-14 8z"/></svg>),
  power: (p) => (<svg viewBox="0 0 24 24" {...p}><path d="M12 3v8"/><path d="M6.3 6.5a8 8 0 1 0 11.4 0"/></svg>),
};

function Icon({ name, className, ...rest }) {
  const make = ICONS[name] || ICONS.brief;
  return make({ className, fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round", strokeLinejoin: "round", ...rest });
}

export default function App() {
  const [page, setPage] = useState("brief");
  const [navOpen, setNavOpen] = useState(false);
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const load = useCallback(() => api.state().then(setState), []);
  useEffect(() => { load(); }, [load]);

  const flash = (m) => { setToast(m); setTimeout(() => setToast(null), 2600); };

  const runCycle = async () => {
    setBusy(true);
    try { const r = await api.run(); setState((s) => ({ ...s, brief: r.brief, scheduler: r.state })); flash("Cycle complete"); }
    catch (e) { flash("Run failed: " + e.message); }
    finally { setBusy(false); load(); }
  };

  const toggleScheduler = async () => {
    if (state?.scheduler?.running) { await api.schedulerStop(); flash("Scheduler stopped"); }
    else { await api.schedulerStart(state?.config?.poll_interval || 300); flash("Scheduler started"); }
    load();
  };

  const giveFeedback = async (claimId, label) => {
    try { await api.feedback(claimId, label); flash("Feedback: " + label); }
    catch (e) { flash("Feedback failed"); }
  };

  // auto-refresh while the scheduler runs (always-on desk)
  useEffect(() => {
    if (!state?.scheduler?.running) return;
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [state?.scheduler?.running, load]);

  if (!state) {
    return <div className="gate"><div className="gate-card"><div className="eyebrow">connecting</div><h1>Research<br/>Desk</h1></div></div>;
  }

  // Always-on intelligence: block on setup until a model is wired up.
  if (state.llm?.needs_setup) {
    return (
      <div className="gate">
        <div className="gate-card">
          <div className="row" style={{ gap: 12, marginBottom: 18 }}>
            <img src="/logo.svg" alt="research-desk" style={{ width: 48, height: 48, borderRadius: 6 }} />
            <div>
              <div className="eyebrow" style={{ margin: 0 }}>Research Desk</div>
              <div style={{ fontSize: 30, lineHeight: 0.9, letterSpacing: 0.02 }}>The intelligence<br />is always on</div>
            </div>
          </div>
          <EngineForm llm={state.llm} onSaved={load} flash={flash} variant="gate" />
        </div>
      </div>
    );
  }

  return (
    <div className={`app ${navOpen ? "nav-open" : ""}`}>
      {navOpen && <div className="scrim" onClick={() => setNavOpen(false)} />}
      <LeftNav page={page} setPage={(p) => { setPage(p); setNavOpen(false); }} state={state} busy={busy} runCycle={runCycle} toggleScheduler={toggleScheduler} />
      <Main page={page} state={state} busy={busy} runCycle={runCycle}
        toggleScheduler={toggleScheduler} giveFeedback={giveFeedback}
        setNavOpen={setNavOpen} load={load} flash={flash} />
      <RightPanel state={state} />
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

/* ---------------- left rail ---------------- */
function LeftNav({ page, setPage, state, busy, runCycle, toggleScheduler }) {
  const ready = state?.llm?.ready;
  const prov = state?.llm?.provider || "heuristic";
  return (
    <nav className="col-left">
      <div className="brand">
        <img src="/logo.svg" alt="research-desk" />
        <div className="word">Research<br /><small>Desk — X intelligence</small>Desk</div>
      </div>
      <div className="nav">
        {PAGES.map((p) => (
          <button key={p.id} className={page === p.id ? "active" : ""} onClick={() => setPage(p.id)}>
            <span className="ico"><Icon name={p.ico} /></span>
            <span className="lbl">{p.label}</span>
          </button>
        ))}
      </div>
      <div className="rail-foot">
        <div className="engine-chip">
          <span className={`dot ${ready ? "on" : ""}`} />
          <div style={{ lineHeight: 1.15 }}>
            <span className="lbl">engine</span>
            <div className="val">{prov === "openai" ? "OpenAI" : prov === "anthropic" ? "Claude" : "Heuristic"}</div>
          </div>
        </div>
        <button className="btn btn-ghost" onClick={toggleScheduler} disabled={!state}>
          <Icon name="power" />
          {state?.scheduler?.running ? "Scheduler live" : "Start scheduler"}
        </button>
        <button className="btn btn-primary" onClick={runCycle} disabled={busy}>
          <Icon name="play" />
          {busy ? "Running…" : "Run cycle"}
        </button>
      </div>
    </nav>
  );
}

/* ---------------- main column ---------------- */
function Main({ page, state, busy, runCycle, toggleScheduler, giveFeedback, setNavOpen, load, flash }) {
  return (
    <main className="col-main">
      <div className="topbar">
        <button className="btn btn-ghost menu-btn" onClick={() => setNavOpen(true)}>☰</button>
        <div>
          <div className="eyebrow">research-desk</div>
          <h2>{PAGES.find((p) => p.id === page)?.label}</h2>
        </div>
        <div className="topbar-actions">
          <span className="row" style={{ gap: 8, fontFamily: "var(--font-mono)", fontSize: 12 }}>
            <span className={`dot ${state?.scheduler?.running ? "on" : ""}`} />
            {state?.scheduler?.running ? "live" : "idle"}
          </span>
        </div>
      </div>
      <div style={{ padding: 18 }}>
        {page === "brief" && <BriefPage state={state} giveFeedback={giveFeedback} />}
        {page === "dash" && <DashPage state={state} />}
        {page === "sources" && <SourcesPage state={state} load={load} flash={flash} />}
        {page === "settings" && <SettingsPage state={state} load={load} flash={flash} />}
      </div>
    </main>
  );
}

/* ---------------- right panel ---------------- */
function RightPanel({ state }) {
  const sch = state?.scheduler;
  const disc = state?.discovery?.discovered || [];
  return (
    <aside className="col-right">
      <div className="surface panel">
        <h3 className="eyebrow">Desk status</h3>
        <div className="row spread">
          <span className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>Engine</span>
          <span className="pill">{state?.llm?.ready ? (state.llm.provider === "openai" ? "OpenAI" : "Claude") : "Heuristic"}</span>
        </div>
        <div className="row spread" style={{ marginTop: 12 }}>
          <span className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>Scheduler</span>
          <span className="row" style={{ gap: 8 }}>
            <span className={`dot ${sch?.running ? "on" : ""}`} />{sch?.running ? "live" : "idle"}
          </span>
        </div>
        {sch?.last_cycle && (
          <div className="row spread" style={{ marginTop: 12 }}>
            <span className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>Last cycle</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{new Date(sch.last_cycle * 1000).toLocaleTimeString()}</span>
          </div>
        )}
        <div className="row spread" style={{ marginTop: 12 }}>
          <span className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>Discovered</span>
          <span>{disc.length}</span>
        </div>
      </div>
      <div className="surface panel">
        <h3 className="eyebrow">Agents</h3>
        {(state?.agents || []).map((a) => (
          <div key={a.name} className="row spread" style={{ padding: "6px 0", borderTop: "1px solid var(--border)" }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.08em" }}>{a.name}</span>
            <span className="muted" style={{ fontSize: 11, maxWidth: 180, textAlign: "right", textTransform: "none" }}>{a.desc}</span>
          </div>
        ))}
      </div>
    </aside>
  );
}

/* ---------------- brief ---------------- */
function BriefPage({ state, giveFeedback }) {
  const md = state?.brief?.markdown || "_No brief yet — run a cycle._";
  const main = parseMarkdownBrief(md);
  return (
    <>
      <div className="eyebrow" style={{ marginBottom: 12 }}>
        {state?.brief?.generated_at ? "Generated " + fmt(state.brief.generated_at) : "No brief generated"}
      </div>
      <h3 className="eyebrow">MAIN BRIEF</h3>
      {main.main.map((it, i) => <BriefCard key={i} it={it} giveFeedback={giveFeedback} />)}
      {!main.main.length && <div className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>Nothing cleared the bar this cycle.</div>}
      <h3 className="eyebrow section-gap">WATCHLIST</h3>
      {main.watch.map((it, i) => (
        <div className="surface panel" key={"w" + i}>
          <div className="brief-head"><span className="headline" style={{ fontSize: 18 }}>{it.headline}</span>
            <span className="conf unconfirmed">watch</span></div>
          {it.why && <div className="why">{it.why}</div>}
        </div>
      ))}
      {!main.watch.length && <div className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>No watch items.</div>}
      <h3 className="eyebrow section-gap">NOISE LOG</h3>
      <div className="surface panel">
        {main.noise.map((n, i) => (
          <div className="noise-item" key={i}>
            <div>{n.text}</div>
            <div className="reason">— {n.reason}</div>
          </div>
        ))}
        {!main.noise.length && <div className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>No items rejected this cycle.</div>}
      </div>
    </>
  );
}

function BriefCard({ it, giveFeedback }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="surface panel brief-card main">
      <div className="brief-head">
        <span className="headline">{it.headline}</span>
        <span className={`conf ${it.confidence}`}>{it.confidence}</span>
      </div>
      {it.why && <div className="why">Why it matters — {it.why}</div>}
      <div className="brief-meta">
        {it.url && <a href={it.url} target="_blank" rel="noreferrer">Primary post ↗</a>}
        {it.time && <span>{it.time}</span>}
        {it.support?.length > 0 && <span>· {it.support.length} supporting</span>}
      </div>
      {it.support?.length > 0 && (
        <div className="support">{it.support.map((s) => <span className="pill" key={s}>@{s}</span>)}</div>
      )}
      <button className="btn btn-ghost" style={{ marginTop: 12, fontSize: 11 }} onClick={() => setOpen((o) => !o)}>
        {open ? "Hide feedback" : "Give feedback"}
      </button>
      {open && it.claimId && (
        <div className="feedback">
          {FEEDBACK_LABELS.map(([l, t]) => (
            <button key={l} className="btn" onClick={() => giveFeedback(it.claimId, l)}>{t}</button>
          ))}
        </div>
      )}
      {open && !it.claimId && <div className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>No claim id on this item.</div>}
    </div>
  );
}

/* ---------------- dashboard ---------------- */
function DashPage({ state }) {
  const stats = state?.stats || {};
  return (
    <>
      <div className="stat-grid">
        <div className="surface stat"><div className="n">{stats.posts || 0}</div><div className="l">Posts ingested</div></div>
        <div className="surface stat"><div className="n">{stats.claims || 0}</div><div className="l">Claims extracted</div></div>
        <div className="surface stat"><div className="n">{stats.sources || 0}</div><div className="l">Sources tracked</div></div>
        <div className="surface stat"><div className="n">{stats.feedback || 0}</div><div className="l">Feedback given</div></div>
      </div>
      <div className="surface panel"><h2>Source trust</h2><TrustBars sources={state?.sources || []} /></div>
      <div className="surface panel"><h2>Source composition</h2><TierDonut sources={state?.sources || []} /></div>
      <div className="surface panel"><h2>Themes you care about</h2><ThemeBars themes={state?.themes || {}} /></div>
    </>
  );
}

/* ---------------- sources ---------------- */
function SourcesPage({ state, load, flash }) {
  const [add, setAdd] = useState("");
  const remove = async (h) => { try { await api.removeWatch(h); load(); } catch (e) { flash(e.message); } };
  return (
    <>
      <div className="surface panel">
        <h2>Watched accounts</h2>
        <div className="row" style={{ marginBottom: 12 }}>
          <input className="inp" placeholder="@handle"
            value={add} onChange={(e) => setAdd(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { api.addWatch(add).then(load); setAdd(""); } }} />
          <button className="btn btn-primary" onClick={async () => { await api.addWatch(add); setAdd(""); load(); }}>Add</button>
        </div>
        <div className="row wrap">
          {(state?.config?.watched_users || []).map((h) => (
            <span className="pill" key={h}>@{h}<span className="x" onClick={() => remove(h)}>✕</span></span>
          ))}
          {!(state?.config?.watched_users || []).length && <span className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>None yet.</span>}
        </div>
      </div>
      <div className="surface panel section-gap"><h2>Source trust graph</h2><TrustBars sources={state?.sources || []} /></div>
    </>
  );
}

/* ---------------- helpers ---------------- */
function fmt(s) {
  const m = /^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/.exec(s || "");
  if (!m) return s;
  return `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]} UTC`;
}

/* Parse the markdown brief into structured items, matching
   vault.render_brief_markdown. */
function parseMarkdownBrief(md) {
  const out = { main: [], watch: [], noise: [] };
  const lines = md.split("\n");
  let section = null;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (/^##\s+MAIN BRIEF/.test(l)) { section = "main"; continue; }
    if (/^##\s+WATCHLIST/.test(l)) { section = "watch"; continue; }
    if (/^##\s+NOISE LOG/.test(l)) { section = "noise"; continue; }
    if (!section) continue;
    if (section === "main") {
      const m = /^###\s+\d+\.\s+(.*)/.exec(l);
      if (m) {
        const it = { headline: m[1], confidence: "unconfirmed", url: "", time: "", support: [], why: "" };
        for (let j = i + 1; j < lines.length && !/^###\s/.test(lines[j]); j++) {
          const wl = lines[j];
          let mm;
          if ((mm = /- \*\*Confidence:\*\*\s*(\w+)/.exec(wl))) it.confidence = mm[1].toLowerCase();
          else if ((mm = /- \*\*Primary post:\*\*\s*(\S+)/.exec(wl))) it.url = mm[1];
          else if ((mm = /- \*\*Time:\*\*\s*(.+)/.exec(wl))) it.time = mm[1];
          else if ((mm = /- \*\*Why it matters:\*\*\s*(.+)/.exec(wl))) it.why = mm[1];
          else if ((mm = /- \*\*Supporting accounts:\*\*\s*(.+)/.exec(wl))) {
            it.support = mm[1].split(",").map((s) => s.trim().replace(/^@/, "")).filter(Boolean);
          }
        }
        out.main.push(it);
      }
    } else if (section === "watch") {
      const m = /^- \*\*(.+?)\*\*\s*—\s*(.*?)\s*\[(\w+)\]\s*(\S*)/.exec(l);
      if (m) out.watch.push({ headline: m[1], why: m[2], confidence: m[3].toLowerCase(), url: m[4] });
    } else if (section === "noise") {
      const m = /^- (.+?) — (.+)/.exec(l);
      if (m) out.noise.push({ text: m[1], reason: m[2] });
    }
  }
  return out;
}
