import React, { useEffect, useState, useCallback } from "react";
import { api } from "./api.js";
import { TrustBars, TierDonut, ThemeBars } from "./charts.jsx";
import { SettingsPage, EngineForm } from "./Settings.jsx";
import { I18nProvider, ThemeProvider, useI18n, useTheme, timeAgo, fmtTime } from "./i18n.jsx";
import { INTEREST_CATEGORIES } from "./interests.js";

const PAGES = [
  { id: "brief", label: "brief", ico: "brief" },
  { id: "dash", label: "dashboard", ico: "dash" },
  { id: "sources", label: "sources", ico: "sources" },
  { id: "settings", label: "settings", ico: "settings" },
];

const FEEDBACK_LABELS = [
  ["useful", "useful"], ["not_useful", "notUseful"],
  ["rumor", "rumor"], ["too_local", "tooLocal"],
  ["too_political", "tooPolitical"], ["want_more", "wantMore"],
];

const THEMES = [
  ["hermes", "Hermes"], ["night", "Night"],
  ["sea", "Sea"], ["ivory", "Ivory"],
];

const TIMEZONES = [
  "Etc/UTC", "America/New_York", "America/Chicago", "America/Los_Angeles",
  "America/Sao_Paulo", "Europe/London", "Europe/Berlin", "Europe/Moscow",
  "Africa/Cairo", "Asia/Tehran", "Asia/Dubai", "Asia/Karachi", "Asia/Kolkata",
  "Asia/Shanghai", "Asia/Tokyo", "Asia/Singapore", "Asia/Bangkok",
  "Australia/Sydney", "Pacific/Auckland",
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
  const [lang, setLang] = useState("en");
  const [theme, setTheme] = useState("hermes");
  return (
    <I18nProvider lang={lang} setLang={setLang}>
      <ThemeProvider theme={theme} setTheme={setTheme}>
        <Desk />
      </ThemeProvider>
    </I18nProvider>
  );
}

function Desk() {
  const { lang, setLang, t } = useI18n();
  const { theme, setTheme } = useTheme();
  const [page, setPage] = useState("brief");
  const [navOpen, setNavOpen] = useState(false);
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const load = useCallback((l) => api.state(l).then(setState).catch(() => {}), []);

  useEffect(() => { load(lang); }, [lang, load]);

  // adopt the saved profile's language/theme once state arrives
  useEffect(() => {
    if (state?.profile) {
      if (state.profile.language && state.profile.language !== lang) setLang(state.profile.language);
      if (state.profile.theme && state.profile.theme !== theme) setTheme(state.profile.theme);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  const flash = (m) => { setToast(m); setTimeout(() => setToast(null), 2600); };

  const changeLang = (l) => {
    setLang(l);
    api.profileSave({ language: l }).catch(() => {});
  };
  const changeTheme = (th) => {
    setTheme(th);
    api.profileSave({ theme: th }).catch(() => {});
  };

  const runCycle = async () => {
    setBusy(true);
    try {
      const r = await api.run();
      setState((s) => ({ ...s, brief: r.brief }));
      flash(t("brief"));
    } catch (e) { flash("run failed: " + e.message); }
    finally { setBusy(false); load(lang); }
  };

  const toggleScheduler = async () => {
    if (state?.scheduler?.running) { await api.schedulerStop(); flash(t("schedulerLive")); }
    else { await api.schedulerStart(state?.config?.poll_interval || 300); flash(t("startScheduler")); }
    load(lang);
  };

  const giveFeedback = async (claimId, label) => {
    try { await api.feedback(claimId, label); flash(t(label)); }
    catch (e) { flash("feedback failed"); }
  };

  // auto-refresh while the scheduler runs (always-on desk)
  useEffect(() => {
    if (!state?.scheduler?.running) return;
    const id = setInterval(() => load(lang), 15000);
    return () => clearInterval(id);
  }, [state?.scheduler?.running, lang, load]);

  if (!state) {
    return <div className="gate"><div className="gate-card"><div className="eyebrow">{t("connecting")}</div><h1>{t("researchDesk")}</h1></div></div>;
  }

  // Always-on intelligence: block on setup until a model is wired up.
  if (state.llm?.needs_setup) {
    return (
      <div className="gate">
        <div className="gate-card">
          <div className="row" style={{ gap: 12, marginBottom: 18 }}>
            <img src="/logo.svg" alt="research-desk" style={{ width: 48, height: 48, borderRadius: 6 }} />
            <div>
              <div className="eyebrow" style={{ margin: 0 }}>{t("researchDesk")}</div>
              <div style={{ fontSize: 30, lineHeight: 0.9, letterSpacing: 0.02 }}>{t("aiEngine")}</div>
            </div>
          </div>
          <EngineForm llm={state.llm} onSaved={() => load(lang)} flash={flash} variant="gate" />
        </div>
      </div>
    );
  }

  // First run: the user must pin their interests before reaching the desk.
  if (state.profile && state.profile.interests_complete === false) {
    return <OnboardingGate state={state} flash={flash} onDone={() => { changeTheme(theme); load(lang); }} />;
  }

  const tz = state.profile?.timezone || "Etc/UTC";
  return (
    <div className={`app ${navOpen ? "nav-open" : ""}`}>
      {navOpen && <div className="scrim" onClick={() => setNavOpen(false)} />}
      <LeftNav page={page} setPage={(p) => { setPage(p); setNavOpen(false); }} state={state} busy={busy} runCycle={runCycle} toggleScheduler={toggleScheduler} />
      <Main page={page} state={state} busy={busy} runCycle={runCycle}
        toggleScheduler={toggleScheduler} giveFeedback={giveFeedback}
        setNavOpen={setNavOpen} load={() => load(lang)} flash={flash}
        lang={lang} changeLang={changeLang} theme={theme} changeTheme={changeTheme} />
      <RightPanel state={state} />
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

/* ---------------- left rail ---------------- */
function LeftNav({ page, setPage, state, busy, runCycle, toggleScheduler }) {
  const { t } = useI18n();
  const ready = state?.llm?.ready;
  const prov = state?.llm?.provider || "heuristic";
  return (
    <nav className="col-left">
      <div className="brand">
        <img src="/logo.svg" alt="research-desk" />
        <div className="word">{t("researchDesk")}<br /><small>{t("brief")} — {t("sources")}</small></div>
      </div>
      <div className="nav">
        {PAGES.map((p) => (
          <button key={p.id} className={page === p.id ? "active" : ""} onClick={() => setPage(p.id)}>
            <span className="ico"><Icon name={p.ico} /></span>
            <span className="lbl">{t(p.label)}</span>
          </button>
        ))}
      </div>
      <div className="rail-foot">
        <div className="engine-chip">
          <span className={`dot ${ready ? "on" : ""}`} />
          <div style={{ lineHeight: 1.15 }}>
            <span className="lbl">{t("engine")}</span>
            <div className="val">{prov === "openai" ? "OpenAI" : prov === "anthropic" ? "Claude" : "Heuristic"}</div>
          </div>
        </div>
        <button className="btn btn-ghost" onClick={toggleScheduler} disabled={!state}>
          <Icon name="power" />
          {state?.scheduler?.running ? t("schedulerLive") : t("startScheduler")}
        </button>
        <button className="btn btn-primary" onClick={runCycle} disabled={busy}>
          <Icon name="play" />
          {busy ? t("running") : t("runCycle")}
        </button>
      </div>
    </nav>
  );
}

/* ---------------- main column ---------------- */
function Main({ page, state, busy, runCycle, toggleScheduler, giveFeedback, setNavOpen, load, flash, lang, changeLang, theme, changeTheme }) {
  const { t } = useI18n();
  return (
    <main className="col-main">
      <div className="topbar">
        <button className="btn btn-ghost menu-btn" onClick={() => setNavOpen(true)}>☰</button>
        <div>
          <div className="eyebrow">{t("researchDesk")}</div>
          <h2>{t(PAGES.find((p) => p.id === page)?.label)}</h2>
        </div>
        <div className="topbar-actions">
          <span className="row" style={{ gap: 8, fontFamily: "var(--font-mono)", fontSize: 12 }}>
            <span className={`dot ${state?.scheduler?.running ? "on" : ""}`} />
            {state?.scheduler?.running ? t("live") : t("idle")}
          </span>
          <span className="lang-btn" role="button" onClick={() => changeLang(lang === "en" ? "fa" : "en")}>{lang === "en" ? "فارسی" : "EN"}</span>
          <span className="theme-swatches">
            {THEMES.map(([tid]) => (
              <button key={tid} className={`swatch ${theme === tid ? "on" : ""}`} data-c={tid}
                title={tid} aria-label={tid} onClick={() => changeTheme(tid)} />
            ))}
          </span>
        </div>
      </div>
      <div style={{ padding: 18 }}>
        {page === "brief" && <BriefPage state={state} giveFeedback={giveFeedback} />}
        {page === "dash" && <DashPage state={state} />}
        {page === "sources" && <SourcesPage state={state} load={load} flash={flash} />}
        {page === "settings" && <SettingsPage state={state} load={load} flash={flash} changeLang={changeLang} changeTheme={changeTheme} />}
      </div>
    </main>
  );
}

/* ---------------- right panel ---------------- */
function RightPanel({ state }) {
  const { t } = useI18n();
  const sch = state?.scheduler;
  const disc = state?.discovery?.discovered || [];
  return (
    <aside className="col-right">
      <div className="surface panel">
        <h3 className="eyebrow">{t("deskStatus")}</h3>
        <div className="row spread">
          <span className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{t("engine")}</span>
          <span className="pill">{state?.llm?.ready ? (state.llm.provider === "openai" ? "OpenAI" : "Claude") : "Heuristic"}</span>
        </div>
        <div className="row spread" style={{ marginTop: 12 }}>
          <span className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{t("schedulerLive")}</span>
          <span className="row" style={{ gap: 8 }}>
            <span className={`dot ${sch?.running ? "on" : ""}`} />{sch?.running ? t("live") : t("idle")}
          </span>
        </div>
        {sch?.last_cycle && (
          <div className="row spread" style={{ marginTop: 12 }}>
            <span className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{t("lastCycle")}</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{new Date(sch.last_cycle * 1000).toLocaleTimeString()}</span>
          </div>
        )}
        <div className="row spread" style={{ marginTop: 12 }}>
          <span className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{t("discovered")}</span>
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
  const { t, lang } = useI18n();
  const tz = state?.profile?.timezone || "Etc/UTC";
  const items = state?.brief?.items || { main: [], watch: [], noise: [] };
  const hasMain = items.main && items.main.length;
  return (
    <>
      <div className="eyebrow" style={{ marginBottom: 12 }}>
        {state?.brief?.generated_at
          ? t("generated") + " " + fmtTime(briefToIso(state.brief.generated_at), tz, lang)
          : t("noBriefGen")}
      </div>
      <h3 className="eyebrow">{t("mainBrief")}</h3>
      {items.main.map((it, i) => <BriefCard key={i} it={it} giveFeedback={giveFeedback} />)}
      {!hasMain && <div className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>{t("nothingCleared")}</div>}
      <h3 className="eyebrow section-gap">{t("watchlist")}</h3>
      {items.watch.map((it, i) => (
        <div className="surface panel" key={"w" + i}>
          <div className="brief-head"><span className="headline" style={{ fontSize: 18 }}>{it.headline}</span>
            <span className="conf unconfirmed">{t("watchlist")}</span></div>
          {it.why && <div className="why">{t("whyItMatters")} — {it.why}</div>}
          {it.url && <div className="brief-meta"><a href={it.url} target="_blank" rel="noreferrer">{t("primaryPost")}</a></div>}
        </div>
      ))}
      {!items.watch.length && <div className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>{t("noWatch")}</div>}
      <h3 className="eyebrow section-gap">{t("noiseLog")}</h3>
      <div className="surface panel">
        {items.noise.map((n, i) => (
          <div className="noise-item" key={i}>
            <div>{n.text}</div>
            <div className="reason">— {n.reason}</div>
          </div>
        ))}
        {!items.noise.length && <div className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>{t("noNoise")}</div>}
      </div>
    </>
  );
}

function BriefCard({ it, giveFeedback }) {
  const { t, lang } = useI18n();
  const tz = it.tz || "Etc/UTC";
  const [open, setOpen] = useState(false);
  const rel = it.ts ? timeAgo(it.ts, tz, lang) : "";
  const abs = it.ts ? fmtTime(it.ts, tz, lang) : "";
  return (
    <div className="surface panel brief-card main">
      <div className="brief-head">
        <span className="headline">{it.headline}</span>
        <span className={`conf ${it.confidence}`}>{it.confidence}</span>
      </div>
      {it.quote && <div className="quote">{it.quote}</div>}
      {it.why && <div className="why">{t("whyItMatters")} — {it.why}</div>}
      <div className="brief-meta">
        {it.url && <a href={it.url} target="_blank" rel="noreferrer">{t("primaryPost")}</a>}
        {abs && <span title={abs}>{rel}</span>}
        {it.support?.length > 0 && <span>· {it.support.length} {t("supporting")}</span>}
      </div>
      {it.support?.length > 0 && (
        <div className="support">{it.support.map((s) => <span className="pill" key={s}>@{s}</span>)}</div>
      )}
      <button className="btn btn-ghost" style={{ marginTop: 12, fontSize: 11 }} onClick={() => setOpen((o) => !o)}>
        {open ? t("hideFeedback") : t("giveFeedback")}
      </button>
      {open && it.claimId && (
        <div className="feedback">
          {FEEDBACK_LABELS.map(([l, key]) => (
            <button key={l} className="btn" onClick={() => giveFeedback(it.claimId, l)}>{t(key)}</button>
          ))}
        </div>
      )}
      {open && !it.claimId && <div className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{t("noClaimId")}</div>}
    </div>
  );
}

/* ---------------- dashboard ---------------- */
function DashPage({ state }) {
  const { t } = useI18n();
  const stats = state?.stats || {};
  return (
    <>
      <div className="stat-grid">
        <div className="surface stat"><div className="n">{stats.posts || 0}</div><div className="l">{t("postsIngested")}</div></div>
        <div className="surface stat"><div className="n">{stats.claims || 0}</div><div className="l">{t("claimsExtracted")}</div></div>
        <div className="surface stat"><div className="n">{stats.sources || 0}</div><div className="l">{t("sourcesTracked")}</div></div>
        <div className="surface stat"><div className="n">{stats.feedback || 0}</div><div className="l">{t("feedbackGiven")}</div></div>
      </div>
      <div className="surface panel"><h2>{t("sourceTrust")}</h2><TrustBars sources={state?.sources || []} /></div>
      <div className="surface panel"><h2>{t("sourceComp")}</h2><TierDonut sources={state?.sources || []} /></div>
      <div className="surface panel"><h2>{t("themesYouCare")}</h2><ThemeBars themes={state?.themes || {}} /></div>
    </>
  );
}

/* ---------------- sources ---------------- */
function SourcesPage({ state, load, flash }) {
  const { t } = useI18n();
  const [add, setAdd] = useState("");
  const remove = async (h) => { try { await api.removeWatch(h); load(); } catch (e) { flash(e.message); } };
  return (
    <>
      <div className="surface panel">
        <h2>{t("watchedAccounts")}</h2>
        <div className="row" style={{ marginBottom: 12 }}>
          <input className="inp" placeholder="@handle"
            value={add} onChange={(e) => setAdd(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { api.addWatch(add).then(load); setAdd(""); } }} />
          <button className="btn btn-primary" onClick={async () => { await api.addWatch(add); setAdd(""); load(); }}>{t("add")}</button>
        </div>
        <div className="row wrap">
          {(state?.config?.watched_users || []).map((h) => (
            <span className="pill" key={h}>@{h}<span className="x" onClick={() => remove(h)}>✕</span></span>
          ))}
          {!(state?.config?.watched_users || []).length && <span className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>{t("noneYet")}</span>}
        </div>
      </div>
      <div className="surface panel section-gap"><h2>{t("sourceTrust")}</h2><TrustBars sources={state?.sources || []} /></div>
    </>
  );
}

/* ---------------- onboarding ---------------- */
function OnboardingGate({ state, flash, onDone }) {
  const { t, lang, setLang } = useI18n();
  const [interests, setInterests] = useState(state?.profile?.interests || []);
  const [instructions, setInstructions] = useState("");
  const [zone, setZone] = useState(state?.profile?.timezone || "Etc/UTC");
  const [saving, setSaving] = useState(false);
  const toggle = (tag) => setInterests((s) => s.includes(tag) ? s.filter((x) => x !== tag) : [...s, tag]);
  const canFinish = interests.length > 0;
  const finish = async () => {
    setSaving(true);
    try {
      await api.profileSave({ interests, user_instructions: instructions, timezone: zone !== state?.profile?.timezone ? zone : null });
      flash(t("profile"));
      onDone();
    } catch (e) { flash("save failed: " + e.message); }
    finally { setSaving(false); }
  };
  return (
    <div className="onboard">
      <div className="onboard-card">
        <div className="onboard-head">
          <div className="eyebrow">{t("researchDesk")}</div>
          <h1>{t("pickInterests")}</h1>
          <p>{t("onboardIntro")}</p>
        </div>
        {INTEREST_CATEGORIES.map((cat) => (
          <div className="int-cat" key={cat.label}>
            <h3>{cat.label}</h3>
            <div>
              {cat.items.map(([tag, label]) => (
                <span key={tag} className={`chip ${interests.includes(tag) ? "on" : ""}`} onClick={() => toggle(tag)}>{label}</span>
              ))}
            </div>
          </div>
        ))}
        <div className="int-cat">
          <h3>{t("searchPrompt")}</h3>
          <textarea className="inp" rows={3} style={{ width: "100%", fontFamily: "var(--font-mono)", boxSizing: "border-box" }}
            placeholder={t("searchPromptHint")} value={instructions}
            onChange={(e) => setInstructions(e.target.value)} />
        </div>
        <div className="row wrap" style={{ gap: 10 }}>
          <div className="field" style={{ flex: 1, marginBottom: 0 }}>
            <label>{t("timezone")}</label>
            <select className="inp" value={zone} onChange={(e) => setZone(e.target.value)}>
              {TIMEZONES.map((z) => <option key={z} value={z}>{z}</option>)}
            </select>
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>{t("language")}</label>
            <button className="btn" onClick={() => setLang(lang === "en" ? "fa" : "en")}>{lang === "en" ? "فارسی" : "English"}</button>
          </div>
        </div>
        <div className="gate-actions" style={{ marginTop: 20 }}>
          <button className="btn btn-primary btn-lg" onClick={finish} disabled={saving || !canFinish}>
            {saving ? "…" : t("finish")}
          </button>
          {!canFinish && <div className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 11, alignSelf: "center" }}>— select at least one interest.</div>}
        </div>
      </div>
    </div>
  );
}

/* ---------------- helpers ---------------- */
function briefToIso(s) {
  // from server brief_YYYYMMDD_HHMMSS (UTC)
  const m = /^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/.exec(s || "");
  if (!m) return s;
  return Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
}
