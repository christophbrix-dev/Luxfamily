import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import type { Lang } from "@/src/data/places";
import type { PersonaId } from "@/src/data/onboarding";
import { storage } from "@/src/utils/storage";
import {
  fetchCurrentUser,
  googleLogout,
  readWebCallbackSessionId,
  cleanWebCallbackUrl,
  finalizeGoogleLogin,
  startGoogleLogin,
  type GoogleAuthUser,
} from "@/src/utils/googleAuth";

const LANG_KEY = "lux.lang";
const LANG_PICKED_KEY = "lux.langPicked";
const SAVED_KEY = "lux.saved";
const USER_KEY = "lux.user";
const BOOKINGS_KEY = "lux.bookings";
const PREFS_KEY = "lux.prefs";
const THEME_KEY = "lux.theme";
const PROFILE_KEY = "lux.profile";
const ONBOARDED_KEY = "lux.onboarded";

export type Preferences = {
  ageRange: [number, number];
  favoriteCantons: string[];
  favoriteCategories: string[];
  notifyOnNew: boolean;
};

const DEFAULT_PREFS: Preferences = {
  ageRange: [0, 12],
  favoriteCantons: [],
  favoriteCategories: [],
  notifyOnNew: false,
};

export type UserProfile = {
  persona: PersonaId | null;
  childAgeGroups: string[];
  interests: string[];
  needs: string[];
  preferredCantons: string[];   // subset of CANTON_OPTIONS ids; empty = all
  budget: string;               // one of BUDGET_OPTIONS ids; "" = not set
  completedAt: number | null;    // null if user skipped
};

const DEFAULT_PROFILE: UserProfile = {
  persona: null,
  childAgeGroups: [],
  interests: [],
  needs: [],
  preferredCantons: [],
  budget: "",
  completedAt: null,
};

export type ThemeMode = "light" | "dark" | "system";

export type User = {
  name: string;
  email: string;
  guest?: boolean;
} | null;

export type Booking = {
  id: string;
  placeId: number;
  date: string;
  adults: number;
  children: number;
  total: number;
  createdAt: number;
};

type Ctx = {
  ready: boolean;
  lang: Lang;
  setLang: (l: Lang) => void;
  user: User;
  signIn: (email: string, name?: string) => void;
  signOutUser: () => void;
  signInGuest: () => void;
  /** Ids of saved entries. Real event ids for API records. */
  saved: string[];
  toggleSave: (id: string) => void;
  bookings: Booking[];
  addBooking: (b: Omit<Booking, "id" | "createdAt">) => Booking;
  preferences: Preferences;
  setPreferences: (p: Preferences) => void;
  theme: ThemeMode;
  setTheme: (t: ThemeMode) => void;
  userProfile: UserProfile;
  setUserProfile: (p: UserProfile) => void;
  hasOnboarded: boolean;
  markOnboarded: () => void;
  resetOnboarding: () => void;
  signInWithGoogle: () => Promise<{ isNewUser: boolean } | null>;
  langPicked: boolean;
  markLangPicked: () => void;
};

const AppCtx = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [lang, setLangState] = useState<Lang>("en");
  const [user, setUser] = useState<User>(null);
  const [saved, setSaved] = useState<string[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [preferences, setPreferencesState] = useState<Preferences>(DEFAULT_PREFS);
  const [theme, setThemeState] = useState<ThemeMode>("light");
  const [userProfile, setUserProfileState] = useState<UserProfile>(DEFAULT_PROFILE);
  const [hasOnboarded, setHasOnboarded] = useState(false);
  const [langPicked, setLangPickedState] = useState(false);

  // Hydrate from storage on mount.
  useEffect(() => {
    (async () => {
      const storedLang = await storage.getItem<string>(LANG_KEY, "");
      if (storedLang && ["en", "de", "fr", "lb"].includes(storedLang)) {
        setLangState(storedLang as Lang);
        setLangPickedState(true);
      }
      const storedLangPicked = await storage.getItem<string>(LANG_PICKED_KEY, "");
      if (storedLangPicked === "true") setLangPickedState(true);
      const storedSaved = await storage.getItem<string>(SAVED_KEY, "[]");
      try {
        const parsed = JSON.parse(storedSaved || "[]");
        if (Array.isArray(parsed)) {
          // Entries used to be stored as the demo records' numeric ids. Those
          // cannot address a real event, so anything non-string is dropped on
          // first launch after the change. Losing a handful of demo favourites
          // is better than keeping ids that point at nothing.
          setSaved(parsed.filter((x): x is string => typeof x === "string"));
        }
      } catch {}
      const storedUser = await storage.getItem<string>(USER_KEY, "");
      if (storedUser) {
        try {
          setUser(JSON.parse(storedUser));
        } catch {}
      }
      const storedBookings = await storage.getItem<string>(BOOKINGS_KEY, "[]");
      try {
        const parsed = JSON.parse(storedBookings || "[]");
        if (Array.isArray(parsed)) setBookings(parsed);
      } catch {}
      const storedPrefs = await storage.getItem<string>(PREFS_KEY, "");
      if (storedPrefs) {
        try {
          setPreferencesState({ ...DEFAULT_PREFS, ...JSON.parse(storedPrefs) });
        } catch {}
      }
      const storedTheme = await storage.getItem<string>(THEME_KEY, "light");
      if (storedTheme === "dark" || storedTheme === "system" || storedTheme === "light") {
        setThemeState(storedTheme);
      }
      const storedProfile = await storage.getItem<string>(PROFILE_KEY, "");
      if (storedProfile) {
        try {
          setUserProfileState({ ...DEFAULT_PROFILE, ...JSON.parse(storedProfile) });
        } catch {}
      }
      const storedOnboarded = await storage.getItem<string>(ONBOARDED_KEY, "");
      setHasOnboarded(storedOnboarded === "1");

      // Google Auth bootstrap:
      // 1. If we just landed back from Emergent redirect (web), exchange the
      //    session_id before doing anything else — it's one-time.
      const callbackSessionId = readWebCallbackSessionId();
      if (callbackSessionId) {
        try {
          const res = await finalizeGoogleLogin(callbackSessionId);
          if (res) {
            const gUser: User = {
              email: res.user.email,
              name: res.user.name || res.user.email.split("@")[0],
              guest: false,
            };
            setUser(gUser);
            storage.setItem(USER_KEY, JSON.stringify(gUser));
          }
        } catch (e) {
          // Silent fail — user sees the login screen and can retry.
          console.warn("Google session exchange failed:", e);
        } finally {
          cleanWebCallbackUrl();
        }
      }

      // 2. Restore session from stored token (if any).
      const g = await fetchCurrentUser();
      if (g) {
        const gUser: User = {
          email: g.email,
          name: g.name || g.email.split("@")[0],
          guest: false,
        };
        setUser(gUser);
        storage.setItem(USER_KEY, JSON.stringify(gUser));
      }

      setReady(true);
    })();
  }, []);

  const setUserProfile = useCallback((p: UserProfile) => {
    setUserProfileState(p);
    storage.setItem(PROFILE_KEY, JSON.stringify(p));
  }, []);

  const markOnboarded = useCallback(() => {
    setHasOnboarded(true);
    storage.setItem(ONBOARDED_KEY, "1");
  }, []);

  const resetOnboarding = useCallback(() => {
    setHasOnboarded(false);
    setUserProfileState(DEFAULT_PROFILE);
    storage.removeItem(ONBOARDED_KEY);
    storage.removeItem(PROFILE_KEY);
  }, []);

  const setPreferences = useCallback((p: Preferences) => {
    setPreferencesState(p);
    storage.setItem(PREFS_KEY, JSON.stringify(p));
  }, []);

  const setTheme = useCallback((t: ThemeMode) => {
    setThemeState(t);
    storage.setItem(THEME_KEY, t);
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    storage.setItem(LANG_KEY, l);
  }, []);

  const markLangPicked = useCallback(() => {
    setLangPickedState(true);
    storage.setItem(LANG_PICKED_KEY, "true");
  }, []);

  const signIn = useCallback((email: string, name?: string) => {
    const next: User = { email, name: name || email.split("@")[0], guest: false };
    setUser(next);
    storage.setItem(USER_KEY, JSON.stringify(next));
  }, []);

  const signInGuest = useCallback(() => {
    const next: User = { email: "guest@local", name: "Guest", guest: true };
    setUser(next);
    storage.setItem(USER_KEY, JSON.stringify(next));
  }, []);

  const signOutUser = useCallback(() => {
    setUser(null);
    storage.removeItem(USER_KEY);
    // Also clear the Emergent Google session (idempotent).
    googleLogout().catch(() => {});
  }, []);

  /**
   * On web: this navigates away and never returns. The session_id lands back
   * at the app root and is picked up by the bootstrap effect.
   * On mobile: waits for the OS auth-session flow to close and exchanges
   * the session_id here. Returns `{ isNewUser }` so the caller can decide
   * to route the user to /onboarding.
   */
  const signInWithGoogle = useCallback(async () => {
    const { sessionId } = await startGoogleLogin();
    if (!sessionId) return null;
    const res = await finalizeGoogleLogin(sessionId);
    if (!res) return null;
    const gUser: User = {
      email: res.user.email,
      name: res.user.name || res.user.email.split("@")[0],
      guest: false,
    };
    setUser(gUser);
    storage.setItem(USER_KEY, JSON.stringify(gUser));
    // "New user" heuristic: they haven't gone through onboarding yet.
    const storedOnboarded = await storage.getItem<string>(ONBOARDED_KEY, "");
    return { isNewUser: storedOnboarded !== "1" };
  }, []);

  const toggleSave = useCallback((id: string) => {
    setSaved((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      storage.setItem(SAVED_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const addBooking = useCallback(
    (b: Omit<Booking, "id" | "createdAt">) => {
      const created: Booking = {
        ...b,
        id: `bk_${Date.now()}`,
        createdAt: Date.now(),
      };
      setBookings((prev) => {
        const next = [created, ...prev];
        storage.setItem(BOOKINGS_KEY, JSON.stringify(next));
        return next;
      });
      return created;
    },
    [],
  );

  const value = useMemo<Ctx>(
    () => ({
      ready,
      lang,
      setLang,
      user,
      signIn,
      signInGuest,
      signOutUser,
      saved,
      toggleSave,
      bookings,
      addBooking,
      preferences,
      setPreferences,
      theme,
      setTheme,
      userProfile,
      setUserProfile,
      hasOnboarded,
      markOnboarded,
      resetOnboarding,
      signInWithGoogle,
      langPicked,
      markLangPicked,
    }),
    [ready, lang, setLang, user, signIn, signInGuest, signOutUser, saved, toggleSave, bookings, addBooking, preferences, setPreferences, theme, setTheme, userProfile, setUserProfile, hasOnboarded, markOnboarded, resetOnboarding, signInWithGoogle, langPicked, markLangPicked],
  );

  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp(): Ctx {
  const ctx = useContext(AppCtx);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}
