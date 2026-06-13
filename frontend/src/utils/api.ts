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
export type LocalizedString = { en: string; de: string; fr: string };

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
  created_at: string;
  updated_at: string;
  created_by?: string | null;
};

export type AdminUser = { id: string; email: string; role: string; name?: string };

export const api = {
  login: (email: string, password: string) =>
    apiFetch<{ access_token: string; user: AdminUser }>("/api/auth/login", {
      method: "POST",
      body: { email, password },
    }),
  me: () => apiFetch<AdminUser>("/api/auth/me", { admin: true }),
  publicEvents: () => apiFetch<ApiEvent[]>("/api/events?upcoming=false"),
  adminEvents: () => apiFetch<ApiEvent[]>("/api/admin/events", { admin: true }),
  createEvent: (payload: Omit<ApiEvent, "id" | "created_at" | "updated_at" | "created_by">) =>
    apiFetch<ApiEvent>("/api/admin/events", { method: "POST", body: payload, admin: true }),
  updateEvent: (id: string, patch: Partial<ApiEvent>) =>
    apiFetch<ApiEvent>(`/api/admin/events/${id}`, { method: "PATCH", body: patch, admin: true }),
  deleteEvent: (id: string) =>
    apiFetch<void>(`/api/admin/events/${id}`, { method: "DELETE", admin: true }),
};
