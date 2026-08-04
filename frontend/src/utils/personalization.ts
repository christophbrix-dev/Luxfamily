/**
 * Personalization helpers — translate an onboarding UserProfile into
 * Events-tab filters and a per-event relevance score.
 *
 * Keep this file pure and side-effect free so it's easy to unit-test.
 */
import type { ApiEvent } from "@/src/utils/api";
import type { UserProfile } from "@/src/contexts/AppContext";

// -----------------------------------------------------------------------------
// Interest tag → matching event categories (DB-side values)
// -----------------------------------------------------------------------------
// Every DB event has `category: string[]`. When any of the mapped strings is
// present, the interest counts as a hit. Kept intentionally lax — a single
// tag can match multiple event categories.
export const INTEREST_TO_CATEGORY: Record<string, string[]> = {
  playgrounds:  ["Playgrounds"],
  animals:      ["Animals"],
  nature:       ["Nature"],
  workshops:    ["Workshops"],
  culture_kids: ["Culture"],
  culture:      ["Culture"],
  landmarks:    ["Culture"],           // no dedicated "Landmarks" category yet
  festivals:    ["Festivals"],
  concerts:     ["Festivals", "Culture"],
  nightlife:    ["Nightlife"],         // future — no events yet
  fine_dining:  ["FineDining", "Food"],
  food:         ["Food"],
  wine:         ["Wine", "Food"],
  sports:       ["Sports"],
  wellness:     ["Wellness"],
  shopping:     ["Shopping"],
};

/**
 * Which family-need filter chip IDs should be auto-activated for a given
 * onboarding profile? Mirrors the state fields on the Events tab.
 */
export type FilterState = {
  wheelchair: boolean;
  sensory: boolean;
  freeParking: boolean;
};

const NEED_TO_FILTER: Record<string, keyof FilterState> = {
  wheelchair:    "wheelchair",
  sensory:       "sensory",
  free_parking:  "freeParking",
};

export function needsToFilters(profile: UserProfile): FilterState {
  const out: FilterState = { wheelchair: false, sensory: false, freeParking: false };
  if (!profile.persona || profile.persona === "skipped") return out;
  for (const n of profile.needs) {
    const key = NEED_TO_FILTER[n];
    if (key) out[key] = true;
  }
  return out;
}

/**
 * How well does one event match the user's stated interests? Returns 0 when
 * the profile is empty/skipped — that way the Events tab falls back to
 * chronological order.
 */
export function eventMatchScore(event: ApiEvent, profile: UserProfile): number {
  if (!profile.persona || profile.persona === "skipped") return 0;

  let score = 0;

  // Interest overlap (main signal)
  if (profile.interests?.length) {
    const cats = event.category ?? [];
    for (const interest of profile.interests) {
      const mapped = INTEREST_TO_CATEGORY[interest] ?? [];
      for (const c of mapped) {
        if (cats.includes(c)) {
          score += 1;
          break;
        }
      }
    }
  }

  // Family age-group bonus
  if (profile.persona === "family") {
    for (const g of profile.childAgeGroups) {
      const [minStr, maxStr] = g.replace("+", "").split("-");
      const min = parseInt(minStr, 10) || 0;
      const max = parseInt(maxStr, 10) || 18;
      if (event.age_max >= min && event.age_min <= max) score += 0.5;
    }
  }

  // Canton match with neighbour-canton tolerance — a Northern user who only
  // ticked "Diekirch" should still see Clervaux and Wiltz events.
  if (profile.preferredCantons?.length) {
    score += cantonAffinity(event.canton, profile.preferredCantons);
  }

  // Budget match — reward events within the user's price ceiling
  if (profile.budget) {
    const budget = BUDGET_LIMITS[profile.budget];
    if (budget !== undefined) {
      if (budget === null || event.price_adult <= budget) {
        // free events get a bigger boost when user asked "free only"
        if (profile.budget === "free" && event.price_adult === 0) score += 1;
        else score += 0.3;
      } else {
        // outside the user's comfort zone
        score -= 0.5;
      }
    }
  }

  return score;
}

// Numeric limits per BUDGET_OPTIONS id — mirrors the data table.
const BUDGET_LIMITS: Record<string, number | null | undefined> = {
  free: 0,
  cheap: 15,
  medium: 30,
  any: null,
};

// Adjacent-canton map — if the user picked a canton, its neighbours count
// as a "soft match" instead of a demotion. Keeps our Northern user seeing
// Clervaux content when they only ticked "Wiltz" or "Diekirch".
const NEIGHBOR_CANTONS: Record<string, string[]> = {
  Luxembourg:         ["Mersch", "Capellen", "Esch-sur-Alzette", "Grevenmacher", "Remich"],
  "Esch-sur-Alzette": ["Luxembourg", "Capellen"],
  Capellen:           ["Luxembourg", "Esch-sur-Alzette", "Mersch", "Redange"],
  Mersch:             ["Luxembourg", "Capellen", "Redange", "Diekirch"],
  Redange:            ["Capellen", "Mersch", "Wiltz"],
  Diekirch:           ["Mersch", "Wiltz", "Clervaux", "Vianden", "Echternach", "Grevenmacher"],
  Vianden:            ["Diekirch", "Clervaux"],
  Wiltz:              ["Redange", "Diekirch", "Clervaux"],
  Clervaux:           ["Wiltz", "Diekirch", "Vianden"],
  Echternach:         ["Diekirch", "Grevenmacher"],
  Grevenmacher:       ["Diekirch", "Echternach", "Remich", "Luxembourg"],
  Remich:             ["Grevenmacher", "Luxembourg"],
};

export function cantonAffinity(eventCanton: string, preferred: string[]): number {
  if (!preferred.length) return 0;
  if (preferred.includes(eventCanton)) return 1;             // direct hit
  for (const p of preferred) {
    if ((NEIGHBOR_CANTONS[p] ?? []).includes(eventCanton)) {
      return 0.4;                                            // neighbouring
    }
  }
  return -0.3;                                               // far away — mild demotion
}

/**
 * Splits events into two lists:
 *   - `forYou`: score > 0, sorted best-first (max 6)
 *   - `others`: everything else, kept in the caller's original order
 * If the profile has no useful signals, `forYou` is empty and `others`
 * equals the input.
 */
export function rankForProfile(
  events: ApiEvent[],
  profile: UserProfile,
): { forYou: ApiEvent[]; others: ApiEvent[]; isPersonalized: boolean } {
  const hasProfile = !!profile.persona && profile.persona !== "skipped";
  if (!hasProfile) return { forYou: [], others: events, isPersonalized: false };

  const scored: { ev: ApiEvent; score: number }[] = events.map((ev) => ({
    ev,
    score: eventMatchScore(ev, profile),
  }));

  const withHits = scored.filter((s) => s.score > 0);
  withHits.sort((a, b) => b.score - a.score);

  // Dedupe by venue-key so crawler-imported near-duplicates of a seeded venue
  // (e.g. 3 different "Sënnesräich" rows) don't monopolise the FOR YOU slots.
  // Venue-key = first two title words, lowercased, punctuation-stripped.
  const venueKey = (title: string): string =>
    title
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\s]+/gu, " ")
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .join(" ");

  const seen = new Set<string>();
  const dedup: ApiEvent[] = [];
  for (const s of withHits) {
    const key = venueKey(s.ev.title?.en ?? s.ev.title?.de ?? "");
    if (key && seen.has(key)) continue;
    seen.add(key);
    dedup.push(s.ev);
    if (dedup.length >= 6) break;
  }

  const forYou = dedup;
  const forYouIds = new Set(forYou.map((e) => e.id));
  const others = events.filter((e) => !forYouIds.has(e.id));

  return { forYou, others, isPersonalized: true };
}
