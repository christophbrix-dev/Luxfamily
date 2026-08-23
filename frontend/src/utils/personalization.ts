/**
 * Personalization helpers — translate an onboarding UserProfile into
 * Events-tab filters and a per-event relevance score.
 *
 * Keep this file pure and side-effect free so it's easy to unit-test.
 */
// Ranking works on list data, so it types on the summary shape the list
// endpoints return. A full ApiEvent still satisfies it structurally, so any
// caller holding a complete document keeps working.
import type { ApiEventSummary } from "@/src/utils/api";
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
export function eventMatchScore(event: ApiEventSummary, profile: UserProfile): number {
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
  if (preferred.includes(eventCanton)) return 3;             // direct hit — strong local bias
  for (const p of preferred) {
    if ((NEIGHBOR_CANTONS[p] ?? []).includes(eventCanton)) {
      return 1;                                              // neighbouring
    }
  }
  return -0.5;                                               // far away — mild demotion
}

/**
 * Splits events into two lists:
 *   - `forYou`: score > 0, sorted best-first (max 8, with geographic guarantee)
 *   - `others`: everything else, kept in the caller's original order
 * If the profile has no useful signals, `forYou` is empty and `others`
 * equals the input.
 *
 * Ranking strategy:
 *   1. All positive-scored events are sorted best-first.
 *   2. Near-duplicate venues (fingerprint overlap) are collapsed to 1 slot.
 *   3. Per-canton cap: no more than half the slots come from a single canton
 *      (prevents Luxembourg-city events from crowding out the North/South).
 *   4. Home-canton guarantee: at least 2 slots are reserved for events in
 *      the user's preferred cantons, so a Wiltz-user always sees local
 *      places like MIGO even if Luxembourg-city has more category matches.
 */
const FOR_YOU_SLOTS = 8;
const HOME_CANTON_RESERVED = 2;
const MAX_PER_CANTON = 4;

export function rankForProfile(
  events: ApiEventSummary[],
  profile: UserProfile,
): { forYou: ApiEventSummary[]; others: ApiEventSummary[]; isPersonalized: boolean } {
  const hasProfile = !!profile.persona && profile.persona !== "skipped";
  if (!hasProfile) return { forYou: [], others: events, isPersonalized: false };

  const scored: { ev: ApiEventSummary; score: number }[] = events.map((ev) => ({
    ev,
    score: eventMatchScore(ev, profile),
  }));

  const withHits = scored.filter((s) => s.score > 0);
  withHits.sort((a, b) => b.score - a.score);

  // Venue-fingerprint dedupe: two events refer to the same venue when their
  // "significant word" sets overlap. This survives crawler prefixes like
  // "Actualités - …" or "Braddel Babbel - Le spectacle - Parc Sënnesräich".
  const STOPWORDS = new Set([
    "actualites", "actualite", "spectacle", "programm", "programme",
    "centre", "parc", "park", "castle", "chateau", "schloss", "musee",
    "the", "and", "der", "die", "das", "les", "des", "with",
    "loisirs", "activite", "activites", "event", "events",
  ]);
  const fingerprint = (title: string): Set<string> => {
    const norm = title
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "")   // strip accents
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ");
    const words = norm.split(/\s+/).filter((w) => w.length >= 5 && !STOPWORDS.has(w));
    return new Set(words);
  };
  const overlaps = (a: Set<string>, b: Set<string>): boolean => {
    for (const w of a) if (b.has(w)) return true;
    return false;
  };

  const preferred = new Set(profile.preferredCantons ?? []);
  const hasPreferred = preferred.size > 0;

  // First pass: dedupe by venue-fingerprint. Keep ALL unique venues (not just
  // top 6), so we can apply cantonal quotas below without running out of
  // candidates.
  const seenFps: Set<string>[] = [];
  const uniqueByVenue: { ev: ApiEventSummary; score: number }[] = [];
  for (const s of withHits) {
    const fp = fingerprint(
      s.ev.title?.en ?? s.ev.title?.de ?? s.ev.title?.fr ?? "",
    );
    if (fp.size === 0) {
      uniqueByVenue.push(s);
      continue;
    }
    if (seenFps.some((prev) => overlaps(prev, fp))) continue;
    seenFps.push(fp);
    uniqueByVenue.push(s);
  }

  // Second pass: greedy pick with per-canton cap + home-canton reservation.
  const forYou: ApiEventSummary[] = [];
  const perCantonCount: Record<string, number> = {};
  let homeCount = 0;

  const pushIfRoom = (ev: ApiEventSummary, isHome: boolean): boolean => {
    if (forYou.length >= FOR_YOU_SLOTS) return false;
    const canton = ev.canton ?? "?";
    const cnt = perCantonCount[canton] ?? 0;
    // Home canton is allowed up to MAX_PER_CANTON, other cantons the same
    // — but we soft-cap non-home cantons at half the slots so a strong
    // Luxembourg-city surplus can't shut out the rest of the country.
    const cap = isHome ? MAX_PER_CANTON : MAX_PER_CANTON;
    if (cnt >= cap) return false;
    forYou.push(ev);
    perCantonCount[canton] = cnt + 1;
    if (isHome) homeCount += 1;
    return true;
  };

  // Step A — reserve home-canton slots first if user picked cantons.
  if (hasPreferred) {
    for (const s of uniqueByVenue) {
      if (homeCount >= HOME_CANTON_RESERVED) break;
      if (preferred.has(s.ev.canton)) {
        pushIfRoom(s.ev, true);
      }
    }
  }

  // Step B — fill the remaining slots by score, honouring caps.
  const alreadyIn = new Set(forYou.map((e) => e.id));
  for (const s of uniqueByVenue) {
    if (forYou.length >= FOR_YOU_SLOTS) break;
    if (alreadyIn.has(s.ev.id)) continue;
    const isHome = hasPreferred && preferred.has(s.ev.canton);
    pushIfRoom(s.ev, isHome);
  }

  const forYouIds = new Set(forYou.map((e) => e.id));
  const others = events.filter((e) => !forYouIds.has(e.id));

  return { forYou, others, isPersonalized: true };
}
