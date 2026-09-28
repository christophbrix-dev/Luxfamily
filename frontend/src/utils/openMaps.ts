// Open a route to a point in the reader's own maps app.
//
// The URL itself is built in mapsUrl.ts, which knows nothing about
// react-native and can therefore be tested for all three platforms.

import { Linking, Platform } from "react-native";

import { mapsUrl } from "@/src/utils/mapsUrl";

/**
 * Open a route to this point.
 *
 * Nothing is thrown at the caller: a device with no maps app is not an error
 * worth an alert, and every call site is a button press that can do nothing
 * rather than break the screen it sits on.
 */
export function openMaps(lat: number, lng: number, label?: string): void {
  void Linking.openURL(mapsUrl(lat, lng, label, Platform.OS)).catch(() => {});
}
