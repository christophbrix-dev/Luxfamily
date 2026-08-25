// Lightweight typed API client. Reads base URL from EXPO_PUBLIC_BACKEND_URL
// and always prefixes endpoints with /api so the Kubernetes ingress routes
// requests to the FastAPI service.

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
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = (data && (data.detail ?? data.message)) || `HTTP ${res.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
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
  price_adult: number;
  price_child: number;
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
  | "price_adult" | "price_child" | "image" | "lat" | "lng"
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
  last_status?: "ok" | "no_events" | "error" | "blocked_by_robots" | null;
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
  publicEvents: () => apiFetch<ApiEventSummary[]>("/api/events?upcoming=true&limit=200"),
  event: (id: string) => apiFetch<ApiEvent>(`/api/events/${id}`),

  /** The OSM taxonomy: group and category names in every language. */
  placesMeta: () => apiFetch<PlacesMeta>("/api/places/meta"),

  /**
   * OSM points of interest.
   *
   * Without a position the backend returns the highest-scoring entries; with
   * one it filters by radius, which is what makes thousands of places usable.
   */
  osmPlaces: (opts: {
    group?: string;
    near?: { lat: number; lng: number };
    radiusKm?: number;
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
