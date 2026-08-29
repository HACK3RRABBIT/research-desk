const BASE = (import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");

async function req(method, path, body) {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const api = {
  state: (lang) => req("GET", "/api/state" + (lang ? `?lang=${lang}` : "")),
  run: () => req("POST", "/api/run"),
  schedulerStart: (interval) =>
    req("POST", "/api/scheduler/start?interval=" + interval),
  schedulerStop: () => req("POST", "/api/scheduler/stop"),
  feedback: (claimId, label) =>
    req("POST", "/api/feedback", { claim_id: claimId, label }),
  addWatch: (handle) => req("POST", "/api/watch", { handle }),
  removeWatch: (handle) => req("DELETE", "/api/watch/" + encodeURIComponent(handle)),
  addKeyword: (kw) => req("POST", "/api/keyword", { keyword: kw }),
  removeKeyword: (kw) => req("DELETE", "/api/keyword/" + encodeURIComponent(kw)),
  engineSave: (cfg) => req("POST", "/api/engine", cfg),
  engineReset: () => req("POST", "/api/engine/reset"),
  engineTest: (cfg) => req("POST", "/api/engine/test", cfg),
  profileSave: (payload) => req("POST", "/api/profile", payload),
  translate: (texts, lang) => req("POST", "/api/translate", { texts, lang }),
};
