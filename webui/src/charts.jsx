import React from "react";

/* Fixed categorical order — never cycled (dataviz skill rule). */
export const TIER_ORDER = [
  "official_gov", "official_company", "primary_journalist",
  "subject_expert", "aggregator", "unknown", "low_trust",
];
const TIER_COLORS = {
  official_gov: "#edff45",
  official_company: "#9a8cff",
  primary_journalist: "#5ee6a2",
  subject_expert: "#ffd166",
  aggregator: "#ff9e6a",
  unknown: "#a2a2c0",
  low_trust: "#ff5c6c",
};

/* Horizontal trust bars: sequential single-hue (accent, light->dark via opacity). */
export function TrustBars({ sources }) {
  return (
    <div>
      {sources.map((s) => (
        <div className="trust-row" key={s.handle}>
          <div className="h" title={s.handle}>@{s.handle}</div>
          <div className="trust-bar">
            <span style={{ width: `${Math.round(s.trust * 100)}%`,
              background: `color-mix(in srgb, var(--accent) ${30 + s.trust * 70}%, transparent)` }} />
          </div>
          <div className="tier">{s.tier.replace("_", " ")}</div>
        </div>
      ))}
      {!sources.length && <div className="muted">No sources yet.</div>}
    </div>
  );
}

/* Source-tier composition: fixed categorical hues, legend always present. */
export function TierDonut({ sources }) {
  const counts = Object.fromEntries(TIER_ORDER.map((t) => [t, 0]));
  sources.forEach((s) => { counts[s.tier] = (counts[s.tier] || 0) + 1; });
  const total = sources.length || 1;
  let acc = 0;
  const segs = TIER_ORDER.filter((t) => counts[t]).map((t) => {
    const frac = counts[t] / total;
    const seg = { t, start: acc, frac };
    acc += frac;
    return seg;
  });
  const R = 54, C = 2 * Math.PI * R;
  return (
    <div>
      <svg className="chart" viewBox="0 0 140 140" style={{ height: 160 }}>
        <g transform="translate(70,70)">
          {segs.map((s) => (
            <circle key={s.t} r={R} fill="none"
              stroke={TIER_COLORS[s.t]} strokeWidth="20"
              strokeDasharray={`${s.frac * C} ${C}`}
              strokeDashoffset={-s.start * C} />
          ))}
        </g>
        <text x="70" y="66" textAnchor="middle" fill="var(--fg)" fontSize="22" fontWeight="700">{sources.length}</text>
        <text x="70" y="84" textAnchor="middle" fill="var(--fg-dim)" fontSize="11" fontFamily="var(--font-mono)" letterSpacing="2">SOURCES</text>
      </svg>
      <div className="legend">
        {segs.map((s) => (
          <span key={s.t}><i style={{ background: TIER_COLORS[s.t] }} />
            {s.t.replace("_", " ")}</span>
        ))}
      </div>
    </div>
  );
}

/* Theme-trend mini bar: categorical themes, fixed order, no color rank mapping. */
export function ThemeBars({ themes }) {
  const items = (themes.boost || []).slice(0, 10);
  const max = Math.max(1, items.length);
  return (
    <div>
      {items.map((t, i) => (
        <div className="trust-row" key={t}>
          <div className="h">{t}</div>
          <div className="trust-bar">
            <span style={{ width: `${Math.round((1 - i / max) * 100)}%`,
              background: "var(--accent)" }} />
          </div>
        </div>
      ))}
      {!items.length && <div className="muted">No themes tracked yet.</div>}
    </div>
  );
}
