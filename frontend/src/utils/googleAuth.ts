/**
 * Emergent-managed Google Auth for our Expo + FastAPI app.
 *
 * Flow:
 *   1. `startGoogleLogin()` navigates to auth.emergentagent.com. On web this
 *      is a full-page navigation; on mobile we use `openAuthSessionAsync`
 *      which pops the platform's OS-provided in-app browser.
 *   2. Emergent redirects back to `redirect_url` with a one-time
 *      `session_id` (in the URL hash on web, in the query string on native).
 *   3. `finalizeGoogleLogin(sessionId)` POSTs it to our backend at
 *      `/api/auth/session`. The backend exchanges it with Emergent for a
 *      7-day session_token and returns { session_token, user }.
 *   4. We persist the token: `expo-secure-store` on native, `localStorage`
 *      on web (never AsyncStorage — unencrypted).
 *
 * Everything below is safe to import on web AND native.
 */
import * as Linking from "expo-linking";
import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import * as WebBrowser from "expo-web-browser";

const RAW = process.env.EXPO_PUBLIC_BACKEND_URL ?? "";
const BASE = RAW.replace(/\/$/, "");
export const SESSION_TOKEN_KEY = "lux.session.token";
const AUTH_ORIGIN = "https://auth.emergentagent.com/";

// Required by expo-web-browser on native so returning to the app after
// authentication completes cleanly.
WebBrowser.maybeCompleteAuthSession();

// -----------------------------------------------------------------------------
// Cross-platform session token storage
// -----------------------------------------------------------------------------
export const sessionStorage = {
  async get(): Promise<string | null> {
    if (Platform.OS === "web") {
      try {
        return typeof window !== "undefined"
          ? window.localStorage.getItem(SESSION_TOKEN_KEY)
          : null;
      } catch {
        return null;
      }
    }
    try {
      return await SecureStore.getItemAsync(SESSION_TOKEN_KEY);
    } catch {
      return null;
    }
  },
  async set(token: string): Promise<void> {
    if (Platform.OS === "web") {
      if (typeof window !== "undefined") {
        window.localStorage.setItem(SESSION_TOKEN_KEY, token);
      }
      return;
    }
    try {
      await SecureStore.setItemAsync(SESSION_TOKEN_KEY, token);
    } catch {}
  },
  async clear(): Promise<void> {
    if (Platform.OS === "web") {
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(SESSION_TOKEN_KEY);
      }
      return;
    }
    try {
      await SecureStore.deleteItemAsync(SESSION_TOKEN_KEY);
    } catch {}
  },
};

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------
export type GoogleAuthUser = {
  id: string;
  email: string;
  name?: string | null;
  picture?: string | null;
  role: string;
};

type ExchangeResponse = { session_token: string; user: GoogleAuthUser };

// -----------------------------------------------------------------------------
// The one exchange endpoint
// -----------------------------------------------------------------------------
async function exchangeSessionId(sessionId: string): Promise<ExchangeResponse> {
  const res = await fetch(`${BASE}/api/auth/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = (data && (data.detail ?? data.message)) || `HTTP ${res.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data as ExchangeResponse;
}

// Guard against processing the same session_id twice (native and web can both
// surface the same one via multiple channels).
const seenSessionIds = new Set<string>();

export async function finalizeGoogleLogin(
  sessionId: string,
): Promise<ExchangeResponse | null> {
  const trimmed = sessionId.trim();
  if (!trimmed || seenSessionIds.has(trimmed)) return null;
  seenSessionIds.add(trimmed);
  const result = await exchangeSessionId(trimmed);
  await sessionStorage.set(result.session_token);
  return result;
}

// -----------------------------------------------------------------------------
// Kick off the OAuth journey
// -----------------------------------------------------------------------------
function buildRedirectUrl(): string {
  if (Platform.OS === "web") {
    // Must point to a route that actually exists in our router. `/` renders
    // the login/landing page and picks up the session_id hash immediately.
    if (typeof window === "undefined") return "";
    return window.location.origin + "/";
  }
  return Linking.createURL("");
}

function buildAuthUrl(redirectUrl: string): string {
  return `${AUTH_ORIGIN}?redirect=${encodeURIComponent(redirectUrl)}`;
}

/**
 * Start the Google login flow. On web this navigates the tab. On mobile it
 * opens the OS in-app browser and waits for the deep-link callback.
 *
 * On mobile, returns `{ sessionId | null }`. On web it returns `null` because
 * the page will have navigated away — the caller doesn't get a chance to run
 * follow-up code.
 */
export async function startGoogleLogin(): Promise<{ sessionId: string | null }> {
  const redirectUrl = buildRedirectUrl();
  const authUrl = buildAuthUrl(redirectUrl);

  if (Platform.OS === "web") {
    // Full-page navigation. Never openAuthSessionAsync on web — cross-origin
    // popups can't hand the session_id back.
    if (typeof window !== "undefined") {
      window.location.href = authUrl;
    }
    return { sessionId: null };
  }

  // Native: install a fallback URL listener BEFORE opening the browser.
  // Android's Chrome Custom Tabs frequently returns { type: "dismiss" } even
  // when the deep-link actually did fire — the listener catches those.
  let capturedUrl: string | null = null;
  const sub = Linking.addEventListener("url", (event) => {
    capturedUrl = event.url;
  });

  try {
    const result = await WebBrowser.openAuthSessionAsync(authUrl, redirectUrl);
    const url =
      (result.type === "success" && result.url) ||
      capturedUrl ||
      (await Linking.getInitialURL());
    return { sessionId: extractSessionId(url ?? "") };
  } finally {
    sub.remove();
  }
}

// -----------------------------------------------------------------------------
// URL parsing helpers — safe to use on both platforms
// -----------------------------------------------------------------------------
export function extractSessionId(rawUrl: string): string | null {
  if (!rawUrl) return null;
  // Emergent returns session_id in the hash fragment OR the query string.
  // Regex over the whole URL matches both cases.
  const m = rawUrl.match(/[?#&]session_id=([^&#]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

/**
 * Called on app cold-start (web only) to check whether we just came back
 * from Emergent's redirect. Returns the session_id if present; the caller
 * should exchange it and then clean the URL.
 */
export function readWebCallbackSessionId(): string | null {
  if (Platform.OS !== "web" || typeof window === "undefined") return null;
  const fromHash = extractSessionId(window.location.hash);
  const fromQuery = extractSessionId(window.location.search);
  return fromHash ?? fromQuery;
}

export function cleanWebCallbackUrl(): void {
  if (Platform.OS !== "web" || typeof window === "undefined") return;
  const url = new URL(window.location.href);
  url.searchParams.delete("session_id");
  // Preserve any existing hash content that isn't the session_id.
  if (url.hash) {
    const cleanedHash = url.hash
      .replace(/[#&]?session_id=[^&]*/, "")
      .replace(/^#&/, "#")
      .replace(/^#$/, "");
    url.hash = cleanedHash;
  }
  window.history.replaceState(
    window.history.state,
    "",
    url.pathname + url.search + url.hash,
  );
}

// -----------------------------------------------------------------------------
// Check for an existing valid session on app mount
// -----------------------------------------------------------------------------
export async function fetchCurrentUser(): Promise<GoogleAuthUser | null> {
  const token = await sessionStorage.get();
  if (!token) return null;
  try {
    const res = await fetch(`${BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      if (res.status === 401) await sessionStorage.clear();
      return null;
    }
    const data = (await res.json()) as GoogleAuthUser;
    return data;
  } catch {
    return null;
  }
}

export async function googleLogout(): Promise<void> {
  const token = await sessionStorage.get();
  if (token) {
    try {
      await fetch(`${BASE}/api/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {}
  }
  await sessionStorage.clear();
}
