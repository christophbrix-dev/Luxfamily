import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import type { Lang } from "@/src/data/places";
import { storage } from "@/src/utils/storage";

const LANG_KEY = "lux.lang";
const SAVED_KEY = "lux.saved";
const USER_KEY = "lux.user";
const BOOKINGS_KEY = "lux.bookings";

export type User = {
  name: string;
  email: string;
  // For demo only; never store plaintext passwords in real apps.
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
  saved: number[];
  toggleSave: (id: number) => void;
  bookings: Booking[];
  addBooking: (b: Omit<Booking, "id" | "createdAt">) => Booking;
};

const AppCtx = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [lang, setLangState] = useState<Lang>("en");
  const [user, setUser] = useState<User>(null);
  const [saved, setSaved] = useState<number[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);

  // Hydrate from storage on mount.
  useEffect(() => {
    (async () => {
      const storedLang = await storage.getItem<string>(LANG_KEY, "en");
      if (storedLang && ["en", "de", "fr"].includes(storedLang)) {
        setLangState(storedLang as Lang);
      }
      const storedSaved = await storage.getItem<string>(SAVED_KEY, "[]");
      try {
        const parsed = JSON.parse(storedSaved || "[]");
        if (Array.isArray(parsed)) setSaved(parsed.filter((n) => typeof n === "number"));
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
      setReady(true);
    })();
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    storage.setItem(LANG_KEY, l);
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
  }, []);

  const toggleSave = useCallback((id: number) => {
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
    }),
    [ready, lang, setLang, user, signIn, signInGuest, signOutUser, saved, toggleSave, bookings, addBooking],
  );

  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp(): Ctx {
  const ctx = useContext(AppCtx);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}
