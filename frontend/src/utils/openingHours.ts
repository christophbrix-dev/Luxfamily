// Is this place open right now?
//
// The point of the app, in Christoph's words: you are out with friends,
// something turned out to be shut, you look at the phone and it tells you
// where to go instead. That only works if "open" means open. A wrong "open"
// sends someone to a second closed door and costs more trust than showing
// nothing at all.
//
// So this answers one of three things, never two:
//
//   "open"     — certain it is open now
//   "closed"   — certain it is closed now
//   "unknown"  — the notation says something we do not fully understand
//
// OSM's opening_hours grammar is much larger than what is implemented here:
// it has seasons, public holidays, school holidays, sunset offsets, week
// numbers, "open ends". Rather than guess at those, anything containing them
// returns "unknown" and the caller shows the raw text instead. Measured
// against the 3,209 values in the Luxembourg extract, the supported subset —
// 24/7, weekday ranges, several time spans, semicolon-joined rules and `off`
// exceptions — covers most of them, and every one it declines to answer is a
// place we simply do not claim anything about.

export type OpenState = "open" | "closed" | "unknown";

/** Mo=0 … Su=6, matching the order OSM writes them in. */
const DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

/**
 * Notation this parser does not implement.
 *
 * Each of these can flip the answer on a given day, so a string containing one
 * is not evaluated at all. "PH off" is the common case: without a Luxembourg
 * holiday calendar there is no way to know whether today counts.
 */
const UNSUPPORTED = /\b(PH|SH|easter|sunrise|sunset|dawn|dusk|week\s+\d)\b|\d{4}|\bJan|\bFeb|\bMar|\bApr|\bMay|\bJun|\bJul|\bAug|\bSep|\bOct|\bNov|\bDec/i;

type Rule = { days: Set<number>; spans: [number, number][]; off: boolean };

/** "09:30" -> 570. Minutes since midnight; 24:00 stays 1440. */
function toMinutes(hhmm: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(hhmm.trim());
  if (!m) return null;
  const h = Number(m[1]);
  const min = Number(m[2]);
  if (h > 24 || min > 59) return null;
  return h * 60 + min;
}

/** "Mo-Fr", "Sa,Su", "We" -> the day numbers they name. */
function parseDays(spec: string): Set<number> | null {
  const out = new Set<number>();
  for (const part of spec.split(",")) {
    const range = /^([A-Za-z]{2})\s*-\s*([A-Za-z]{2})$/.exec(part.trim());
    if (range) {
      const from = DAYS.findIndex((d) => d.toLowerCase() === range[1].toLowerCase());
      const to = DAYS.findIndex((d) => d.toLowerCase() === range[2].toLowerCase());
      if (from < 0 || to < 0) return null;
      // Fr-Mo wraps around the end of the week.
      for (let i = from; ; i = (i + 1) % 7) {
        out.add(i);
        if (i === to) break;
      }
      continue;
    }
    const single = DAYS.findIndex((d) => d.toLowerCase() === part.trim().toLowerCase());
    if (single < 0) return null;
    out.add(single);
  }
  return out.size ? out : null;
}

/** "09:00-12:00,14:00-18:00" -> [[540,720],[840,1080]]. */
function parseSpans(spec: string): [number, number][] | null {
  const spans: [number, number][] = [];
  for (const part of spec.split(",")) {
    const m = /^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$/.exec(part.trim());
    if (!m) return null;
    const from = toMinutes(m[1]);
    const to = toMinutes(m[2]);
    if (from === null || to === null) return null;
    spans.push([from, to]);
  }
  return spans.length ? spans : null;
}

function parseRules(value: string): Rule[] | null {
  const rules: Rule[] = [];
  for (const raw of value.split(";")) {
    const rule = raw.trim();
    if (!rule) continue;

    // "Su off" / "Mo-Fr closed": an exception carved out of an earlier rule.
    const offMatch = /^(.*?)\s+(off|closed)$/i.exec(rule);
    if (offMatch) {
      const days = parseDays(offMatch[1]);
      if (!days) return null;
      rules.push({ days, spans: [], off: true });
      continue;
    }

    // "Mo-Fr 09:00-18:00" — days then spans.
    const withDays = /^([A-Za-z]{2}[A-Za-z,\s-]*?)\s+([\d:,\s-]+)$/.exec(rule);
    if (withDays) {
      const days = parseDays(withDays[1]);
      const spans = parseSpans(withDays[2]);
      if (!days || !spans) return null;
      rules.push({ days, spans, off: false });
      continue;
    }

    // "09:00-18:00" with no days means every day.
    const spans = parseSpans(rule);
    if (spans) {
      rules.push({ days: new Set([0, 1, 2, 3, 4, 5, 6]), spans, off: false });
      continue;
    }

    return null; // something we do not understand: decline the whole string
  }
  return rules.length ? rules : null;
}

/**
 * Whether `value` says the place is open at `at`.
 *
 * Later rules win over earlier ones, which is how OSM defines them: in
 * "Mo-Su 10:00-18:00; Su off" the Sunday closure overrides the range.
 */
export function isOpenAt(value: string | null | undefined, at: Date = new Date()): OpenState {
  const text = (value ?? "").trim();
  if (!text) return "unknown";
  if (text === "24/7") return "open";
  if (UNSUPPORTED.test(text)) return "unknown";

  const rules = parseRules(text);
  if (!rules) return "unknown";

  // JS counts Sunday as 0; OSM counts Monday first.
  const day = (at.getDay() + 6) % 7;
  const minutes = at.getHours() * 60 + at.getMinutes();

  let state: OpenState = "closed";
  for (const rule of rules) {
    if (!rule.days.has(day)) continue;
    if (rule.off) {
      state = "closed";
      continue;
    }
    for (const [from, to] of rule.spans) {
      // 22:00-02:00 runs past midnight.
      const inside = from <= to
        ? minutes >= from && minutes < to
        : minutes >= from || minutes < to;
      if (inside) state = "open";
    }
  }
  return state;
}

/** A short label, or null when there is nothing honest to say. */
export function openLabel(
  value: string | null | undefined,
  lang: "en" | "de" | "fr" | "lb",
  at: Date = new Date(),
): string | null {
  const state = isOpenAt(value, at);
  if (state === "unknown") return null;
  const words = {
    open: { en: "Open now", de: "Jetzt geöffnet", fr: "Ouvert", lb: "Elo op" },
    closed: { en: "Closed", de: "Geschlossen", fr: "Fermé", lb: "Zou" },
  } as const;
  return words[state][lang];
}
