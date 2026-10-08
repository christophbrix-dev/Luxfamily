// Lightweight typed API client. Reads base URL from EXPO_PUBLIC_BACKEND_URL
// and always prefixes endpoints with /api so the Kubernetes ingress routes
// requests to the FastAPI service.

import { ApiError, describeHttpError, readBody } from "@/src/utils/apiError";
import { buildEventQuery, type EventQuery } from "@/src/utils/eventQuery";
import { storage } from "@/src/utils/storage";

const RAW = process.env.EXPO_PUBLIC_BACKEND_URL ?? "";
const BASE = RAW.replace(/\/$/, "");

const ADMIN_TOKEN_KEY = "lux.admin.token";

export async function getAdminToken(): Promise<string | null> {
  return (await storage.getItem<string>(ADMIN_TOKEN_KEY, "")) || null;
}

export async function setAdminToken(token: string | null): Promise<void> {
  if (!token) await storage.removeItem(ADMIN_TOKEN_KEY);
  else await storage.setItem(ADMIN_TOKEN_KEY, token);
}

type FetchOpts = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  admin?: boolean; // attach admin JWT if true
};

export { ApiError };

export async function apiFetch<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.admin) {
    const token = await getAdminToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 204) return undefined as unknown as T;

  const text = await res.text();

  // Not every response is JSON, and assuming so turned a plain "404 page not
  // found" from a gateway into "Unexpected non-whitespace character after JSON
  // at position 4" on the user's screen — because "404" parses as a number and
  // the rest of the sentence does not. Anything that is not our own API
  // answering can arrive as HTML or text: a proxy, a maintenance page, a
  // container that has not started.
  const { data, parsed } = readBody(text);

  if (!res.ok) {
    throw new ApiError(res.status, describeHttpError(res.status, data, parsed ? "" : text));
  }
  if (text && !parsed) {
    // A 200 that is not JSON means something answered in our place.
    throw new ApiError(res.status, `Unexpected reply from ${BASE || "the server"}`);
  }
  return data as T;
}

// ----- Types matching FastAPI EventResponse -----
// Same shape as the one in src/data/places, deliberately: values move between
// the two and a mismatch shows up as an unfixable assignment error.
export type LocalizedString = { en: string; de: string; fr: string; lb?: string };

export type ApiEvent = {
  id: string;
  title: LocalizedString;
  short: LocalizedString;
  description: LocalizedString;
  type: "Event" | "Indoor" | "Outdoor" | "Educational";
  canton: string;
  town: string;
  category: string[];
  age_min: number;
  age_max: number;
  start_date: string;
  end_date?: string | null;
  time: string;
  // null when the page never said. A zero here reads as "free", which is what
  // every imported event used to claim — 528 of them, some costing 30 €.
  price_adult: number | null;
  price_child: number | null;
  price_free?: boolean;
  price_source?: "event" | "unknown";
  age_source?: "event" | "source" | "unknown";
  price_label: LocalizedString;
  accessibility: LocalizedString;
  weather_fit: LocalizedString;
  image: string;
  lat: number;
  lng: number;
  bookable: boolean;
  published: boolean;
  rating: number;
  featured: boolean;
  featured_until?: string | null;
  view_count: number;
  source_id?: string | null;
  source_name?: string | null;
  external_id?: string | null;
  website_url: string;
  accessibility_wheelchair: boolean;
  sensory_friendly: boolean;
  free_parking: boolean;
  sensory_notes: LocalizedString;
  parking: LocalizedString;
  food_allowed: boolean;
  food_onsite: LocalizedString;
  preparation_tips: LocalizedString;
  payment_methods: string[];
  opening_hours: LocalizedString;
  peak_hours: LocalizedString;
  changing_facilities: boolean;
  restrooms: boolean;
  created_at: string;
  updated_at: string;
  created_by?: string | null;
};

// What the list endpoints return. The long localized prose (description,
// accessibility, parking, preparation_tips, opening_hours, …) lives only on the
// detail endpoint — sending it for every row made the list payload roughly
// three times bigger than it needed to be.
export type ApiEventSummary = Pick<
  ApiEvent,
  | "id" | "title" | "short" | "type" | "canton" | "town" | "category"
  | "age_min" | "age_max" | "start_date" | "end_date" | "time"
  | "price_adult" | "price_child" | "price_free" | "price_source"
  | "age_source" | "image" | "lat" | "lng"
  | "featured" | "published" | "rating" | "view_count"
  | "accessibility_wheelchair" | "sensory_friendly" | "free_parking"
> & { source_name?: string | null };

// One OpenStreetMap point of interest. The ingest holds thousands of these —
// playgrounds, parks, pools, museums — and nothing displayed them until now.
export type ApiPlace = {
  id: string;
  slug: string;
  kind: string;
  group: string;
  name: string;
  lat: number | null;
  lng: number | null;
  age_min: number;
  age_max: number;
  family_score: number;
  website_url: string;
  phone: string;
  opening_hours: string;
  wheelchair: boolean;
  toilets: boolean;
  source_ref: string;
  source_license: string;
  /**
   * A route's shape, one polyline per member way — hiking and cycle routes
   * only, and only when `geometry` was asked for. 865 of the places are these,
   * and they carry no lat/lng at all: a trail is a line, and the distance to it
   * is the distance to its nearest point.
   */
  path_parts?: number[][][];
  /**
   * Kilometres from the position that was sent, present only when one was.
   *
   * The server ranked on this number, so the screen shows it rather than
   * recomputing a second one from lat/lng. Both use the same haversine and
   * would usually agree — and "usually" is how a list ends up ordered by one
   * number and labelled with another.
   */
  distance_km?: number;
};

/** Group and category labels, translated by the backend taxonomy. */
export type PlaceLabels = {
  label_de: string;
  label_fr: string;
  label_lb: string;
  label_en: string;
};

export type PlacesMeta = {
  groups: Record<string, PlaceLabels & { color: string }>;
  categories: Record<string, PlaceLabels & { group: string; base_score: number }>;
};

export type ApiSource = {
  id: string;
  name: string;
  kind: "ical" | "data_public_lu" | "html_scraper" | "json_ld" | "sitemap";
  url: string;
  active: boolean;
  canton_default: string;
  town_default: string;
  category_default: string[];
  age_min_default: number;
  age_max_default: number;
  lat_default: number;
  lng_default: number;
  image_default: string;
  selectors?: Record<string, string> | null;
  created_at: string;
  last_run_at?: string | null;
  // "no_events": the run succeeded and parsed nothing at all. Distinct from
  // "ok" with zero imports, which happens whenever a calendar is simply quiet.
  //
  // "blocked_by_robots" and "robots_unreadable" are also a pair that looks
  // like one thing: in both the source was not crawled, which is correct. But
  // the first means the site told us not to, and the second means its
  // robots.txt timed out and we never got to ask. One has to be dropped from
  // the list, the other retried — and for a week both read "robots.txt says
  // no" on the admin screen, which claimed two communes had refused us.
  last_status?:
    | "ok"
    | "no_events"
    | "error"
    | "blocked_by_robots"
    | "robots_unreadable"
    | null;
  last_error?: string | null;
  last_imported_count?: number | null;
  last_skipped_count?: number | null;
  /** inserted + skipped: what the page yielded before any filtering. */
  last_seen_count?: number | null;
  /** Consecutive runs that yielded nothing. Reset by the first event seen. */
  empty_runs?: number | null;
};

export type Analytics = {
  total_events: number;
  published: number;
  drafts: number;
  featured: number;
  total_views: number;
  top_events: { id: string; title: string; view_count: number }[];
};

export type AdminUser = { id: string; email: string; role: string; name?: string };

/** The server's own cap. Asking for more is a 422, not a bigger page. */
const PAGE = 200;

/**
 * How many pages we are ever willing to walk. Four is 800 events, comfortably
 * more than the whole calendar holds today, and a ceiling that cannot turn a
 * mis-specified filter into an unbounded loop.
 */
const MAX_PAGES = 4;

/**
 * Every event matching `query`, not just the first page of them.
 *
 * The app used to ask for `limit=200` once and filter what came back. The
 * calendar has held more than 200 upcoming events since the crawlers were
 * fixed, so a bit under half of it was invisible — and nothing looked wrong,
 * because a truncated list is a perfectly good-looking list.
 *
 * Paging stops on a short page rather than on a total. `apiFetch` returns the
 * parsed body and not the headers, so X-Total-Count is out of reach here, and
 * "fewer rows than we asked for" means the same thing without needing it.
 */
async function fetchAllEvents(query?: EventQuery): Promise<ApiEventSummary[]> {
  const filters = buildEventQuery(query);
  const prefix = `/api/events${filters ? `${filters}&` : "?"}upcoming=true&limit=${PAGE}`;

  const out: ApiEventSummary[] = [];
  for (let page = 0; page < MAX_PAGES; page += 1) {
    const batch = await apiFetch<ApiEventSummary[]>(`${prefix}&skip=${page * PAGE}`);
    out.push(...batch);
    if (batch.length < PAGE) break;
  }
  return out;
}

export const api = {
  login: (email: string, password: string) =>
    apiFetch<{ access_token: string; user: AdminUser }>("/api/auth/login", {
      method: "POST",
      body: { email, password },
    }),
  me: () => apiFetch<AdminUser>("/api/auth/me", { admin: true }),

  /**
   * Change the signed-in admin's password.
   *
   * The current one is sent as well as the new one: the backend requires it,
   * because a seven-day token sitting in browser storage should not be enough
   * to lock the owner out of their own account.
   */
  changePassword: (currentPassword: string, newPassword: string) =>
    apiFetch<void>("/api/admin/password", {
      method: "POST",
      admin: true,
      body: { current_password: currentPassword, new_password: newPassword },
    }),
  // List endpoints return ApiEventSummary, not the full document. Every field
  // the list screens currently read is included; anything else needs the detail
  // endpoint (or a new field on the backend's EventSummary).
  // upcoming=true, not false. The backend caps limit at 200 and sorts featured
  // first, then by date ascending — so with upcoming=false the 200 rows that
  // come back are the *oldest* ones. Against the live database that was 200
  // events and not one of them in the future: an empty calendar, a "near you"
  // row of things that already happened, and no sign anything was wrong.
  // Every screen here asks "what is on", which is what this flag means.
  publicEvents: (query?: EventQuery) => fetchAllEvents(query),
  event: (id: string) => apiFetch<ApiEvent>(`/api/events/${id}`),

  /** The OSM taxonomy: group and category names in every language. */
  placesMeta: () => apiFetch<PlacesMeta>("/api/places/meta"),

  /**
   * OSM points of interest.
   *
   * Without a position the backend returns the highest-scoring entries; with
   * one it returns the nearest first, inside a real circle, each row carrying
   * its `distance_km`. It used to return the best-scored entries in a square
   * around the position, which meant a playground 200 m away could lose to a
   * park 10 km away, and a "10 km" search could answer with 13 km.
   */
  osmPlaces: (opts: {
    group?: string;
    near?: { lat: number; lng: number };
    radiusKm?: number;
    /** Ask for route shapes too. Only the map draws them — they were 70 KB of
     *  a 331 KB answer, for 39 rows out of 300. */
    geometry?: boolean;
    limit?: number;
    skip?: number;
  } = {}) => {
    const q = new URLSearchParams();
    if (opts.group) q.set("group", opts.group);
    if (opts.near) {
      q.set("near_lat", String(opts.near.lat));
      q.set("near_lng", String(opts.near.lng));
      q.set("radius_km", String(opts.radiusKm ?? 10));
    }
    if (opts.geometry) q.set("geometry", "true");
    q.set("limit", String(opts.limit ?? 60));
    if (opts.skip) q.set("skip", String(opts.skip));
    return apiFetch<ApiPlace[]>(`/api/places?${q.toString()}`);
  },
  pingView: (id: string) =>
    apiFetch<void>(`/api/events/${id}/view`, { method: "POST" }),
  adminEvents: () => apiFetch<ApiEventSummary[]>("/api/admin/events?limit=500", { admin: true }),
  adminEvent: (id: string) =>
    apiFetch<ApiEvent>(`/api/admin/events/${id}`, { admin: true }),
  createEvent: (payload: Omit<ApiEvent, "id" | "created_at" | "updated_at" | "created_by">) =>
    apiFetch<ApiEvent>("/api/admin/events", { method: "POST", body: payload, admin: true }),
  updateEvent: (id: string, patch: Partial<ApiEvent>) =>
    apiFetch<ApiEvent>(`/api/admin/events/${id}`, { method: "PATCH", body: patch, admin: true }),
  deleteEvent: (id: string) =>
    apiFetch<void>(`/api/admin/events/${id}`, { method: "DELETE", admin: true }),
  adminSources: () => apiFetch<ApiSource[]>("/api/admin/sources", { admin: true }),
  createSource: (payload: Omit<ApiSource, "id" | "created_at" | "last_run_at" | "last_status" | "last_error" | "last_imported_count" | "last_skipped_count">) =>
    apiFetch<ApiSource>("/api/admin/sources", { method: "POST", body: payload, admin: true }),
  updateSource: (id: string, patch: Partial<ApiSource>) =>
    apiFetch<ApiSource>(`/api/admin/sources/${id}`, { method: "PATCH", body: patch, admin: true }),
  deleteSource: (id: string) =>
    apiFetch<void>(`/api/admin/sources/${id}`, { method: "DELETE", admin: true }),
  runSource: (id: string) =>
    apiFetch<{ last_status: string; last_imported_count: number; last_error?: string }>(
      `/api/admin/sources/${id}/run`,
      { method: "POST", admin: true },
    ),
  runAllSources: () =>
    apiFetch<{ runs: unknown[] }>(`/api/admin/sources/run-all`, { method: "POST", admin: true }),
  robotsCheck: (url: string) =>
    apiFetch<{
      url: string;
      host: string;
      user_agent: string;
      allowed: boolean;
      crawl_delay_seconds: number;
      applied_min_delay_seconds: number;
    }>("/api/admin/sources/robots-check", {
      method: "POST",
      body: { url },
      admin: true,
    }),
  analytics: () => apiFetch<Analytics>("/api/admin/analytics/overview", { admin: true }),
};
