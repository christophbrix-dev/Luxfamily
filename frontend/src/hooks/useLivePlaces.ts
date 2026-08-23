// Shared loader for the event list, in the shape the screens already render.
//
// Home, Saved and Calendar all want the same list. Each fetching separately
// would mean three requests for one dataset on every tab switch, so the result
// is held in a module-level cache and handed to whoever asks. A pull-to-refresh
// on any screen refreshes it for all of them.
//
// Screens that used `PLACES` from src/data/places can swap in `usePlaces()` and
// otherwise stay as they are.

import { useCallback, useEffect, useMemo, useState } from "react";

import type { Place } from "@/src/data/places";
import { distanceKm, useUserLocation } from "@/src/hooks/useUserLocation";
import { api } from "@/src/utils/api";
import { toPlaces } from "@/src/utils/toPlace";

type State = {
  places: Place[] | null;
  error: string | null;
};

let cache: State = { places: null, error: null };
let inFlight: Promise<void> | null = null;
const listeners = new Set<(s: State) => void>();

function publish(next: State) {
  cache = next;
  listeners.forEach((notify) => notify(next));
}

async function load(force = false): Promise<void> {
  if (!force && cache.places) return;
  // Several screens mounting at once must not trigger several requests.
  if (inFlight) return inFlight;

  inFlight = (async () => {
    try {
      const events = await api.publicEvents();
      publish({ places: toPlaces(events), error: null });
    } catch (e: unknown) {
      publish({
        places: cache.places, // keep what we had rather than blanking the screen
        error: e instanceof Error ? e.message : "Failed to load",
      });
    } finally {
      inFlight = null;
    }
  })();
  return inFlight;
}

/**
 * The live event list.
 *
 * `places` is null while the first load is running, so a screen can tell
 * "loading" from "loaded and genuinely empty" — the two deserve different
 * messages.
 */
export function usePlaces() {
  const [state, setState] = useState<State>(cache);
  const { coords } = useUserLocation();

  useEffect(() => {
    listeners.add(setState);
    void load();
    return () => {
      listeners.delete(setState);
    };
  }, []);

  const refresh = useCallback(() => load(true), []);

  // Distance is filled in only once the user has shared a position. Without one
  // the field stays undefined and the screens hide it, rather than showing a
  // number that means nothing.
  const places = useMemo(() => {
    if (!state.places || !coords) return state.places;
    return state.places.map((p) =>
      p.lat && p.lng
        ? { ...p, distanceKm: distanceKm(coords, { lat: p.lat, lng: p.lng }) }
        : p,
    );
  }, [state.places, coords]);

  return {
    places,
    error: state.error,
    loading: state.places === null && state.error === null,
    hasLocation: coords !== null,
    refresh,
  };
}

/** Drop the cache — for tests, and after an admin edit. */
export function resetPlacesCache() {
  publish({ places: null, error: null });
}
