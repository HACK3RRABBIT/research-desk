import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import { useI18n } from "./i18n.jsx";
import { INTEREST_CATEGORIES } from "./interests.js";

const PROVIDERS = [
  ["openai", "OpenAI-compatible"],
  ["anthropic", "Anthropic / Claude"],
  ["heuristic", "Heuristic (offline)"],
];

const TIMEZONES = [
  "Etc/UTC", "America/New_York", "America/Chicago", "America/Los_Angeles",
  "America/Sao_Paulo", "Europe/London", "Europe/Berlin", "Europe/Moscow",
  "Africa/Cairo", "Asia/Tehran", "Asia/Dubai", "Asia/Karachi", "Asia/Kolkata",
  "Asia/Shanghai", "Asia/Tokyo", "Asia/Singapore", "Asia/Bangkok",
  "Australia/Sydney", "Pacific/Auckland",
];

const noop = () => {};

/* Engine configuration form — shared by the first-run setup gate and the
   Settings page. Reads the masked engine block from /api/state and drives
   /api/engine (save), /api/engine/reset, and /api/engine/test. */
export function EngineForm({ llm, onSaved = noop, flash = noop, variant = "settings", busy = false }) {
  const { t } = useI18n();
  const [provider, setProvider] = useState(llm?.provider || "openai");
  const [baseUrl, setBaseUrl] = useState(llm?.base_url || "");
  const [model, setModel] = useState(llm?.model || "");
  const [apiKey, setApiKey] = useState("");
  const [temperature, setTemperature] = useState(0);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    setProvider(llm?.provider || "openai");
    setBaseUrl(llm?.base_url || "");
    setModel(llm?.model || "");
    setTemperature(llm?.temperature ?? 0);
    setMaxTokens(llm?.max_tokens ?? 1024);
  }, [llm]);

  const save = async () => {
    const body = {
      provider, base_url: baseUrl.trim(), model: model.trim(),
      temperature, max_tokens: Number(maxTokens),
      ...(apiKey ? { api_key: apiKey } : {}),
    };
    try {
      const r = await api.engineSave(body);
      flash("Engine saved — “" + (r.llm?.provider || provider) + "”");
      setApiKey("");
      onSaved();
    } catch (e) {
      flash("Save failed: " + e.message);
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      const r = await api.engineTest({
        provider, base_url: baseUrl.trim(), model: model.trim(),
        api_key: apiKey, timeout: 30,
      });
      flash((r.ok ? "✓ " : "✗ ") + (r.message || "Done"));
    } catch (e) {
      flash("Test failed: " + e.message);
    } finally {
      setTesting(false);
    }
  };

  const reset = async () => {
    try {
      await api.engineReset();
      flash("Returned to Heuristic engine");
      setApiKey("");
      onSaved();
    } catch (e) {
      flash("Reset failed: " + e.message);
    }
  };

  return (
    <div className="surface panel">
      <h3 className="eyebrow">{t("aiEngine")}</h3>
      {variant === "gate" && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 30, lineHeight: 0.95, letterSpacing: 0.02 }}>
            Wire up your model
          </div>
          <div className="body" style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--fg-dim)", marginTop: 8, lineHeight: 1.5 }}>
            The desk's intelligence is always on. Point it at any OpenAI-compatible
            endpoint (OpenAI, OpenRouter, vLLM, LM Studio, Ollama…) — base URL, API
            key, and model. The key is stored locally and never leaves this machine.
          </div>
        </div>
      )}

      <div className="field">
        <label>{t("provider")}</label>
        <select className="inp" value={provider} disabled={busy}
          onChange={(e) => setProvider(e.target.value)}>
          {PROVIDERS.map(([v, lbl]) => <option key={v} value={v}>{lbl}</option>)}
        </select>
      </div>

      <div className="field">
        <label>{t("baseUrl")}</label>
        <input className="inp" value={baseUrl} disabled={busy}
          placeholder="https://api.openai.com/v1"
          onChange={(e) => setBaseUrl(e.target.value)} />
        {!baseUrl && (
          <div className="body" style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--fg-dim)", marginTop: 6, lineHeight: 1.5 }}>
            Local models: Ollama → http://localhost:11434/v1 · LM Studio → http://localhost:1234/v1 · vLLM / unsloth GGUF server. No API key needed.
          </div>
        )}
      </div>

      <div className="field">
        <label>{t("modelName")}</label>
        <input className="inp" value={model} disabled={busy}
          placeholder="gpt-4o-mini"
          onChange={(e) => setModel(e.target.value)} />
      </div>

      <div className="field">
        <label>{t("apiKey")} {llm?.has_key ? `— set (${llm.key_hint})` : "(optional for local servers)"}</label>
        <input className="inp" type="password" value={apiKey} disabled={busy}
          placeholder={llm?.has_key ? "Leave blank to keep current key" : "sk-…"}
          autoComplete="new-password"
          onChange={(e) => setApiKey(e.target.value)} />
      </div>

      <div className="row" style={{ gap: 14, alignItems: "flex-end" }}>
        <div className="field" style={{ flex: 1 }}>
          <label>{t("temperature")}</label>
          <input className="inp" type="number" min="0" max="2" step="0.1"
            value={temperature} disabled={busy}
            onChange={(e) => setTemperature(Number(e.target.value))} />
        </div>
        <div className="field" style={{ flex: 1 }}>
          <label>{t("maxTokens")}</label>
          <input className="inp" type="number" min="1" max="8192"
            value={maxTokens} disabled={busy}
            onChange={(e) => setMaxTokens(Number(e.target.value))} />
        </div>
      </div>

      <div className="gate-actions">
        <button className="btn btn-primary" disabled={busy} onClick={save}>{t("saveEngine")}</button>
        <button className="btn" disabled={busy || testing} onClick={test}>
          {testing ? t("testing") : t("testConnection")}
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={reset}>{t("resetHeuristic")}</button>
      </div>
    </div>
  );
}

/* Settings page: Profile + AI Engine + watched keywords + general config. */
export function SettingsPage({ state, load, flash, changeLang, changeTheme }) {
  const { t } = useI18n();
  const [kw, setKw] = useState("");
  const cfg = state?.config || {};
  const watch = async (fn) => { try { await fn(); load(); } catch (e) { flash(e.message); } };

  return (
    <>
      <ProfilePanel state={state} flash={flash} load={load} changeLang={changeLang} changeTheme={changeTheme} />

      <EngineForm llm={state?.llm} onSaved={load} flash={flash} />

      <div className="surface panel section-gap">
        <h3 className="eyebrow">{t("watchedKeywords")}</h3>
        <div className="row" style={{ marginBottom: 12 }}>
          <input className="inp" placeholder="keyword"
            value={kw} onChange={(e) => setKw(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { watch(() => api.addKeyword(kw)); setKw(""); } }} />
          <button className="btn btn-primary" onClick={async () => { await watch(() => api.addKeyword(kw)); setKw(""); }}>{t("add")}</button>
        </div>
        <div className="row wrap">
          {(cfg.watched_keywords || []).map((k) => (
            <span className="pill" key={k}>{k}
              <span className="x" onClick={() => watch(() => api.removeKeyword(k))}>✕</span></span>
          ))}
        </div>
      </div>

      <div className="surface panel section-gap">
        <h3 className="eyebrow">{t("configuration")}</h3>
        <Row k="RSSHub base" v={cfg.rsshub_base_url} />
        <Row k="Poll interval" v={`${cfg.poll_interval}s`} />
        <Row k="Languages" v={(cfg.languages || []).join(", ")} />
        <Row k="Discovery" v={state?.discovery?.enabled ? "auto (on)" : "off"} />
      </div>
    </>
  );
}

function ProfilePanel({ state, flash, load, changeLang, changeTheme }) {
  const { t, lang, setLang } = useI18n();
  const prof = state?.profile || {};
  const [interests, setInterests] = useState(prof.interests || []);
  const [instructions, setInstructions] = useState(prof.user_instructions || "");
  const [zone, setZone] = useState(prof.timezone || "Etc/UTC");
  const toggle = (tag) => setInterests((s) => s.includes(tag) ? s.filter((x) => x !== tag) : [...s, tag]);

  const save = async () => {
    try {
      await api.profileSave({
        interests,               // always send; empty list clears the tags
        user_instructions: instructions,
        timezone: zone,
      });
      flash(t("profile"));
      load();
    } catch (e) { flash("save failed: " + e.message); }
  };

  return (
    <div className="surface panel">
      <h3 className="eyebrow">{t("profile")}</h3>
      <div className="row" style={{ gap: 14, flexWrap: "wrap", marginBottom: 14 }}>
        <div className="field" style={{ flex: 1, marginBottom: 0, minWidth: 160 }}>
          <label>{t("language")}</label>
          <button className="btn" onClick={() => setLang(lang === "en" ? "fa" : "en")}>{lang === "en" ? "فارسی" : "English"}</button>
        </div>
        <div className="field" style={{ flex: 2, marginBottom: 0, minWidth: 200 }}>
          <label>{t("timezone")}</label>
          <select className="inp" value={zone} onChange={(e) => setZone(e.target.value)}>
            {TIMEZONES.map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
        </div>
      </div>

      <div className="field">
        <label>{t("yourInterests")}</label>
        <div style={{ maxHeight: 240, overflow: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
          {INTEREST_CATEGORIES.map((cat) => (
            <div key={cat.label}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.2em", color: "var(--fg-dim)", textTransform: "uppercase", marginBottom: 6 }}>{cat.label}</div>
              <div className="row wrap" style={{ gap: 8 }}>
                {cat.items.map(([tag, label]) => (
                  <span key={tag} className={`chip ${interests.includes(tag) ? "on" : ""}`} onClick={() => toggle(tag)}>{label}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="field">
        <label>{t("instructions")}</label>
        <textarea className="inp" rows={3} style={{ width: "100%", fontFamily: "var(--font-mono)", boxSizing: "border-box" }}
          placeholder={t("instructionsHint")} value={instructions}
          onChange={(e) => setInstructions(e.target.value)} />
      </div>

      <div className="gate-actions">
        <button className="btn btn-primary" onClick={save}>{t("saveProfile")}</button>
      </div>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="row spread" style={{ padding: "8px 0", borderTop: "1px solid var(--border)" }}>
      <span className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: 12, letterSpacing: "0.06em" }}>{k}</span>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600 }}>{v || "—"}</span>
    </div>
  );
}
