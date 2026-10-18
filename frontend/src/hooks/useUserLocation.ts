// The user's coarse position, if they have agreed to share it.
//
// Everything here is optional by design. The app worked without a location
// before and still does: distances simply stay hidden and "near you" falls back
// to plain order. Nothing is gated behind the permission, and nothing nags —
// asking is a deliberate act by the user, not something that happens on launch.
//
// Accuracy is requested at the "balanced" level, roughly a few hundred metres.
// That is plenty to say how far a playground is and avoids asking the device
// for a precision the app has no use for.

import * as Location from "expo-location";
import { useCallback, useEffect, useState } from "react";

import { storage } from "@/src/utils/storage";

const ASKED_KEY = "lux.location.asked";

export type Coords = { lat: number; lng: number };

export type LocationState = {
  coords: Coords | null;
  /** "granted" once we have a position, "denied" if refused, "unasked" before. */
  status: "unasked" | "granted" | "denied" | "loading";
};

let cache: LocationState = { coords: null, status: "unasked" };
const listeners = new Set<(s: LocationState) => void>();

function publish(next: LocationState) {
  cache = next;
  listeners.forEach((notify) => notify(next));
}

/**
 * Read the position, asking for permission if it has not been asked before.
 *
 * `interactive` distinguishes a user pressing "find things near me" from the
 * app checking on mount. Only the first may raise the system prompt; the second
 * uses an already-granted permission or does nothing.
 */
async function locate(interactive: boolean): Promise<void> {
  try {
    const existing = await Location.getForegroundPermissionsAsync();
    let granted = existing.granted;

    if (!granted) {
      // Never prompt on our own. A dialog nobody asked for gets dismissed, and
      // on iOS a dismissed prompt cannot be raised again from the app.
      if (!interactive || !existing.canAskAgain) {
        publish({ coords: null, status: existing.canAskAgain ? "unasked" : "denied" });
        return;
      }
      const asked = await Location.requestForegroundPermissionsAsync();
      granted = asked.granted;
      await storage.setItem(ASKED_KEY, "1");
    }

    if (!granted) {
      publish({ coords: null, status: "denied" });
      return;
    }

    publish({ coords: cache.coords, status: "loading" });
    const pos = await Location.getLastKnownPositionAsync()
      ?? await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });

    publish({
      coords: pos ? { lat: pos.coords.latitude, lng: pos.coords.longitude } : null,
      status: pos ? "granted" : "denied",
    });
  } catch {
    // A device with location switched off, or a simulator with none set. Not an
    // error worth showing: the app simply carries on without distances.
    publish({ coords: null, status: "denied" });
  }
}

export function useUserLocation() {
  const [state, setState] = useState<LocationState>(cache);

  useEffect(() => {
    listeners.add(setState);
    // Non-interactive: picks up a permission granted earlier, never prompts.
    void locate(false);
    return () => {
      listeners.delete(setState);
    };
  }, []);

  /** Ask for permission. Call this from a button the user pressed. */
  const request = useCallback(() => locate(true), []);

  return { ...state, request };
}

// Re-exported rather than written twice. It moved to src/utils/viewport.ts,
// which imports nothing and can therefore be run by a test script under plain
// node; this hook cannot. Two copies of a distance formula is exactly the
// shape of drift this project keeps paying for.
export { distanceKm } from "@/src/utils/viewport";
