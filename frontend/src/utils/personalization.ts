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

  // Canton match — meaningful boost when user narrowed down
  if (profile.preferredCantons?.length) {
    if (profile.preferredCantons.includes(event.canton)) {
      score += 1;
    } else {
      // outside preferred cantons — significant demotion but keep the event
      score -= 0.5;
    }
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

  const scored: Array<{ ev: ApiEvent; score: number }> = events.map((ev) => ({
    ev,
    score: eventMatchScore(ev, profile),
  }));

  const withHits = scored.filter((s) => s.score > 0);
  withHits.sort((a, b) => b.score - a.score);

  const forYou = withHits.slice(0, 6).map((s) => s.ev);
  const forYouIds = new Set(forYou.map((e) => e.id));
  const others = events.filter((e) => !forYouIds.has(e.id));

  return { forYou, others, isPersonalized: true };
}
