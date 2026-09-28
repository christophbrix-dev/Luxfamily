// The URL that opens a route to a point, per platform.
//
// Deliberately free of any react-native import: the platform arrives as an
// argument, so this can be exercised for iOS, Android and the web from a plain
// node script. The side effect — actually opening the link — lives next door in
// openMaps.ts, which is three lines and has nothing to get wrong.
//
// What this replaces: all four "open in maps" buttons built the same
// openstreetmap.org/?mlat=… link, which is a web page with a pin on it. On a
// phone that is a browser tab, not Apple Maps and not Google Maps, and there is
// no route in it. The button promised navigation and delivered a picture.

/** "ios" | "android" | anything else, which is treated as the web. */
export type MapsPlatform = string;

export function mapsUrl(
  lat: number,
  lng: number,
  label: string | undefined,
  os: MapsPlatform,
): string {
  const point = `${lat},${lng}`;

  if (os === "ios") {
    // `daddr` is the destination; Apple Maps fills in the start itself, which
    // is what turns this from a pin into a route. `maps://` would work too,
    // but only when the scheme is declared in LSApplicationQueriesSchemes, and
    // a link that silently fails is worse than one that goes the long way.
    const named = label ? `&q=${encodeURIComponent(label)}` : "";
    return `https://maps.apple.com/?daddr=${point}${named}`;
  }

  if (os === "android") {
    // `geo:` is the platform's own scheme: it opens whichever maps app the
    // user has chosen rather than the one we would have picked for them, which
    // matters on a device that may not have Google Maps at all. The label in
    // brackets is what the pin is called once it opens.
    const named = label ? `${point}(${label})` : point;
    return `geo:${point}?q=${encodeURIComponent(named)}`;
  }

  // The web. OpenStreetMap's directions page routes, unlike the pin link this
  // replaces, and it keeps the app on the same map data it draws its tiles from.
  return `https://www.openstreetmap.org/directions?to=${encodeURIComponent(point)}`;
}
