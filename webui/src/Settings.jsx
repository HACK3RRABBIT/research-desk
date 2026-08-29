import React, { useEffect, useState } from "react";
import { api } from "./api.js";

const PROVIDERS = [
  ["openai", "OpenAI-compatible"],
  ["anthropic", "Anthropic / Claude"],
  ["heuristic", "Heuristic (offline)"],
];

const noop = () => {};

/* Engine configuration form — shared by the first-run setup gate and the
   Settings page. Reads the masked engine block from /api/state and drives
   /api/engine (save), /api/engine/reset, and /api/engine/test. */
export function EngineForm({ llm, onSaved = noop, flash = noop, variant = "settings", busy = false }) {
  const [provider, setProvider] = useState(llm?.provider || "openai");
  const [baseUrl, setBaseUrl] = useState(llm?.base_url || "");
  const [model, setModel] = useState(llm?.model || "");
  const [apiKey, setApiKey] = useState("");
  const [temperature, setTemperature] = useState(0);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [testing, setTesting] = useState(false);

  // Sync from the server whenever the masked engine block changes (e.g. after
  // a save or reset) — but never overwrite an in-progress key the user typed.
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
      // Only send a key when the user typed one; otherwise keep the existing.
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
      const r = await api.engineReset();
      flash("Returned to Heuristic engine");
      setApiKey("");
      onSaved();
    } catch (e) {
      flash("Reset failed: " + e.message);
    }
  };

  return (
    <div className="surface panel">
      <h3 className="eyebrow">AI Engine — always on</h3>
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
        <label>PROVIDER</label>
        <select className="inp" value={provider} disabled={busy}
          onChange={(e) => setProvider(e.target.value)}>
          {PROVIDERS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
      </div>

      <div className="field">
        <label>BASE URL</label>
        <input className="inp" value={baseUrl} disabled={busy}
          placeholder="https://api.openai.com/v1"
          onChange={(e) => setBaseUrl(e.target.value)} />
      </div>

      <div className="field">
        <label>MODEL NAME</label>
        <input className="inp" value={model} disabled={busy}
          placeholder="gpt-4o-mini"
          onChange={(e) => setModel(e.target.value)} />
      </div>

      <div className="field">
        <label>API KEY {llm?.has_key ? `— set (${llm.key_hint})` : "(optional for local servers)"}</label>
        <input className="inp" type="password" value={apiKey} disabled={busy}
          placeholder={llm?.has_key ? "Leave blank to keep current key" : "sk-…"}
          autoComplete="new-password"
          onChange={(e) => setApiKey(e.target.value)} />
      </div>

      <div className="row" style={{ gap: 14, alignItems: "flex-end" }}>
        <div className="field" style={{ flex: 1 }}>
          <label>TEMPERATURE</label>
          <input className="inp" type="number" min="0" max="2" step="0.1"
            value={temperature} disabled={busy}
            onChange={(e) => setTemperature(Number(e.target.value))} />
        </div>
        <div className="field" style={{ flex: 1 }}>
          <label>MAX TOKENS</label>
          <input className="inp" type="number" min="1" max="8192"
            value={maxTokens} disabled={busy}
            onChange={(e) => setMaxTokens(Number(e.target.value))} />
        </div>
      </div>

      <div className="gate-actions">
        <button className="btn btn-primary" disabled={busy} onClick={save}>Save engine</button>
        <button className="btn" disabled={busy || testing} onClick={test}>
          {testing ? "Testing…" : "Test connection"}
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={reset}>Reset to Heuristic</button>
      </div>
    </div>
  );
}

/* Settings page: AI Engine + watched keywords + general config. */
export function SettingsPage({ state, load, flash }) {
  const [kw, setKw] = useState("");
  const cfg = state?.config || {};
  const watch = async (fn) => { try { await fn(); load(); } catch (e) { flash(e.message); } };

  return (
    <>
      <EngineForm llm={state?.llm} onSaved={load} flash={flash} />

      <div className="surface panel section-gap">
        <h3 className="eyebrow">Watched keywords</h3>
        <div className="row" style={{ marginBottom: 12 }}>
          <input className="inp" placeholder="keyword"
            value={kw} onChange={(e) => setKw(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { watch(() => api.addKeyword(kw)); setKw(""); } }} />
          <button className="btn btn-primary" onClick={async () => { await watch(() => api.addKeyword(kw)); setKw(""); }}>Add</button>
        </div>
        <div className="row wrap">
          {(cfg.watched_keywords || []).map((k) => (
            <span className="pill" key={k}>{k}
              <span className="x" onClick={() => watch(() => api.removeKeyword(k))}>✕</span></span>
          ))}
        </div>
      </div>

      <div className="surface panel section-gap">
        <h3 className="eyebrow">Configuration</h3>
        <Row k="RSSHub base" v={cfg.rsshub_base_url} />
        <Row k="Poll interval" v={`${cfg.poll_interval}s`} />
        <Row k="Languages" v={(cfg.languages || []).join(", ")} />
        <Row k="Discovery" v={state?.discovery?.enabled ? "auto (on)" : "off"} />
      </div>
    </>
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
