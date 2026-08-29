import React, { createContext, useContext, useEffect } from "react";

/* ------------------------------------------------------------------
   Strings + language context. `t(key)` returns the current-language
   string, falling back to English. Persian (fa) also flips <html dir=rtl>
   so the whole app renders right-aligned with Vazirmatn.
   ------------------------------------------------------------------ */

const S = {
  brief:           { en: "Brief",            fa: "خلاصه" },
  dashboard:       { en: "Dashboard",        fa: "داشبورد" },
  sources:         { en: "Sources",          fa: "منابع" },
  settings:        { en: "Settings",         fa: "تنظیمات" },
  connecting:      { en: "connecting",       fa: "در حال اتصال" },
  researchDesk:    { en: "Research Desk",    fa: "میز پژوهش" },
  engine:          { en: "engine",           fa: "موتور" },
  runCycle:        { en: "Run cycle",        fa: "اجرای چرخه" },
  running:         { en: "Running…",         fa: "در حال اجرا…" },
  schedulerLive:   { en: "Scheduler live",   fa: "زمان‌بند فعال" },
  startScheduler:  { en: "Start scheduler",  fa: "شروع زمان‌بند" },
  live:            { en: "live",             fa: "فعال" },
  idle:            { en: "idle",             fa: "آماده" },
  deskStatus:      { en: "Desk status",      fa: "وضعیت میز" },
  lastCycle:       { en: "Last cycle",       fa: "آخرین چرخه" },
  discovered:      { en: "Discovered",       fa: "کشف‌شده" },
  noBrief:         { en: "No brief yet — run a cycle.", fa: "هنوز خلاصه‌ای نیست — یک چرخه اجرا کنید." },
  noBriefGen:      { en: "No brief generated", fa: "خلاصه‌ای تولید نشده" },
  generated:       { en: "Generated",        fa: "تولید شد" },
  mainBrief:       { en: "MAIN BRIEF",       fa: "خلاصه اصلی" },
  watchlist:       { en: "WATCHLIST",        fa: "فهرست پایش" },
  noiseLog:        { en: "NOISE LOG",        fa: "گزارش حذف‌ها" },
  nothingCleared:  { en: "Nothing cleared the bar this cycle.", fa: "هیچ خبری این چرخه معیار را رد نکرد." },
  noWatch:         { en: "No watch items.",  fa: "موردی برای پایش نیست." },
  noNoise:         { en: "No items rejected this cycle.", fa: "موردی رد نشد." },
  whyItMatters:    { en: "Why it matters",   fa: "چرا مهم است" },
  primaryPost:     { en: "Primary post ↗",   fa: "پست اصلی ↗" },
  supporting:      { en: "supporting",       fa: "تأییدکننده" },
  giveFeedback:    { en: "Give feedback",    fa: "بازخورد" },
  hideFeedback:    { en: "Hide feedback",    fa: "پنهان‌کردن بازخورد" },
  useful:          { en: "Useful",           fa: "مفید" },
  notUseful:       { en: "Not useful",       fa: "کم‌فایده" },
  rumor:           { en: "Rumor",            fa: "شایعه" },
  tooLocal:        { en: "Too local",        fa: "خیلی محلی" },
  tooPolitical:    { en: "Too political",    fa: "خیلی سیاسی" },
  wantMore:        { en: "Want more",        fa: "بیشتر" },
  noClaimId:       { en: "No claim id on this item.", fa: "شناسه ادعا برای این مورد نیست." },
  postsIngested:   { en: "Posts ingested",   fa: "پست‌های دریافت‌شده" },
  claimsExtracted: { en: "Claims extracted", fa: "ادعاهای استخراج‌شده" },
  sourcesTracked:  { en: "Sources tracked",  fa: "منابع ردیابی‌شده" },
  feedbackGiven:   { en: "Feedback given",   fa: "بازخورد داده‌شده" },
  sourceTrust:     { en: "Source trust",     fa: "اعتماد به منابع" },
  sourceComp:      { en: "Source composition", fa: "ترکیب منابع" },
  themesYouCare:   { en: "Themes you care about", fa: "موضوع‌های مورد علاقه" },
  watchedAccounts: { en: "Watched accounts", fa: "حساب‌های پایش‌شده" },
  add:             { en: "Add",              fa: "افزودن" },
  noneYet:         { en: "None yet.",        fa: "هنوز هیچ." },
  addKeyword:      { en: "Add keyword",      fa: "افزودن کلیدواژه" },
  watchedKeywords: { en: "Watched keywords", fa: "کلیدواژه‌های پایش" },
  configuration:   { en: "Configuration",    fa: "پیکربندی" },
  saveEngine:      { en: "Save engine",      fa: "ذخیره موتور" },
  testConnection:  { en: "Test connection",  fa: "تست اتصال" },
  testing:         { en: "Testing…",         fa: "در حال تست…" },
  resetHeuristic:  { en: "Reset to Heuristic", fa: "بازگشت به هوش ساده" },
  aiEngine:        { en: "AI Engine — always on", fa: "موتور هوش مصنوعی — همیشه روشن" },
  provider:        { en: "PROVIDER",         fa: "ارائه‌دهنده" },
  baseUrl:         { en: "BASE URL",         fa: "آدرس پایه" },
  modelName:       { en: "MODEL NAME",       fa: "نام مدل" },
  apiKey:          { en: "API KEY",          fa: "کلید API" },
  temperature:     { en: "TEMPERATURE",      fa: "دما" },
  maxTokens:       { en: "MAX TOKENS",       fa: "بیشترین توکن" },
  profile:         { en: "Profile",          fa: "پروفایل" },
  language:        { en: "Language",         fa: "زبان" },
  timezone:        { en: "Timezone",         fa: "منطقه زمانی" },
  theme:           { en: "Theme",            fa: "پوسته" },
  yourInterests:   { en: "Your interests",   fa: "علاقه‌های شما" },
  instructions:    { en: "Manual directive", fa: "دستورالعمل دستی" },
  instructionsHint:{ en: "Tell the AI exactly what to search for (optional).", fa: "به هوش مصنوعی بگویید دقیقاً چه چیزی را جستجو کند (اختیاری)." },
  saveProfile:     { en: "Save profile",     fa: "ذخیره پروفایل" },
  finish:          { en: "Finish & open the desk", fa: "پایان و باز کردن میز" },
  pickInterests:   { en: "Pick what you care about", fa: "موضوع‌های مورد علاقه را انتخاب کنید" },
  onboardIntro:    { en: "Choose the topics you want the desk to watch. The more you pick, the more precisely it finds important, verified news for you. You can change these later.", fa: "موضوع‌هایی را که می‌خواهید میز پایش کند انتخاب کنید. هر چه بیشتر انتخاب کنید، دقیق‌تر اخبار مهم و تأییدشده را برای شما پیدا می‌کند. بعداً قابل تغییر است." },
  searchPrompt:    { en: "What should the desk focus on?", fa: "میز روی چه چیزی تمرکز کند؟" },
  searchPromptHint:{ en: "e.g. “The impact of sanctions on oil prices; primary statements from central banks and energy ministries.”", fa: "مثلاً: «تأثیر تحریم‌ها بر قیمت نفت؛ بیانیه‌های رسمی بانک‌های مرکزی و وزارت‌های انرژی.»" },
  skip:            { en: "Skip for now",     fa: "رد کردن فعلاً" },
  noSources:       { en: "No sources yet.",  fa: "هنوز منبعی نیست." },
  noThemes:        { en: "No themes tracked yet.", fa: "موضوعی ردیابی نشده است." },
  nothingWatch:    { en: "No watch items.",  fa: "موردی برای پایش نیست." },
  primaryPostLink: { en: "Original post",    fa: "پست اصلی" },
  timeAgoOpts:     { en: "ago",              fa: "پیش" },
};

const I18nCtx = createContext({ lang: "en", t: (k) => k });
const ThemeCtx = createContext({ theme: "hermes", setTheme: () => {} });

export function I18nProvider({ lang = "en", setLang = () => {}, children }) {
  const t = (k) => (S[k] && S[k][lang]) || S[k]?.en || k;
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("lang", lang);
    root.setAttribute("dir", lang === "fa" ? "rtl" : "ltr");
  }, [lang]);
  return (
    <I18nCtx.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nCtx.Provider>
  );
}

export function ThemeProvider({ theme = "hermes", setTheme = () => {}, children }) {
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);
  return (
    <ThemeCtx.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeCtx.Provider>
  );
}

export const useI18n = () => useContext(I18nCtx);
export const useTheme = () => useContext(ThemeCtx);

/* ------------------------------------------------------------------
   Time formatting. The server hands timestamps as ISO (UTC); we render
   relative "X min ago" + an absolute time in the user's timezone.
   ------------------------------------------------------------------ */
export function timeAgo(ts, tz = "Etc/UTC", lang = "en") {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d)) return ts;
  let locale = lang === "fa" ? "fa-IR" : "en-US";
  const diff = (Date.now() - d.getTime()) / 1000;
  const minutes = Math.floor(diff / 60);
  try {
    const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
    if (minutes < 1) return lang === "fa" ? "همین حالا" : "just now";
    if (minutes < 60) return rtf.format(-minutes, "minute");
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return rtf.format(-hours, "hour");
    const days = Math.floor(hours / 24);
    if (days < 30) return rtf.format(-days, "day");
    return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tz }).format(d);
  } catch {
    return new Intl.DateTimeFormat(locale, { dateStyle: "short", timeZone: tz }).format(d);
  }
}

export function fmtTime(ts, tz = "Etc/UTC", lang = "en") {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d)) return ts;
  let locale = lang === "fa" ? "fa-IR" : "en-US";
  try {
    return new Intl.DateTimeFormat(locale, {
      dateStyle: "medium", timeStyle: "short", timeZone: tz,
    }).format(d);
  } catch {
    return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(d);
  }
}
