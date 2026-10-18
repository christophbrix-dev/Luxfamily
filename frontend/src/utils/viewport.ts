// Which entries belong to the part of the map you are looking at.
//
// The places layer has followed the map since it was written: pan, and the
// pins for the new view are fetched. The event list did not. It was one
// request for the whole country, filtered afterwards by canton and search box
// only — so zooming to Esch-sur-Alzette left Vianden at the top of the list,
// sixty kilometres away and on nobody's screen.
//
// Nothing is re-fetched for this. The app already holds every event: the list
// is paged through to the end on load, so the whole calendar is in memory and
// the filter is arithmetic, not a round trip.
//
// No imports, so scripts/test-viewport.mjs can run it under plain node.

export type Coords = { lat: number; lng: number };

export type View = {
  lat: number;
  lng: number;
  zoom: number;
  /** Half the diagonal of the visible area. */
  radiusKm: number;
};

/**
 * Below this, the list shows everything.
 *
 * The country view sits at zoom 9 and its circle does not cover the whole of
 * Luxembourg — the country is about 82 km tall and half a diagonal is less
 * than that. Filtering there would quietly drop Clervaux and Esch from a list
 * the reader has not narrowed in any way, which is the opposite of helpful.
 * From 10 upwards the reader has chosen a region, and the list follows.
 */
export const FOLLOW_FROM_ZOOM = 10;

export function followsView(view: View | null): view is View {
  return view !== null && view.zoom >= FOLLOW_FROM_ZOOM;
}

/**
 * Great-circle distance in kilometres.
 *
 * The haversine formula, which treats the earth as a sphere. Across Luxembourg
 * that is accurate to a few metres — far below the accuracy of anything it is
 * given here.
 */
export function distanceKm(a: Coords, b: Coords): number {
  const R = 6371;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.sin(dLng / 2) ** 2 * Math.cos(lat1) * Math.cos(lat2);
  return 2 * R * Math.asin(Math.sqrt(h));
}

/**
 * Is this coordinate inside the view?
 *
 * The circle is drawn a little wider than the visible rectangle — the radius
 * is half the diagonal, so the corners are inside it and a pin just past the
 * edge is kept. Erring outward is the right way round: a list that drops
 * something the reader can see on the map is a bug they will notice, and one
 * that keeps something just off-screen is not.
 *
 * An entry with no coordinates stays in the list. We do not know where it is,
 * and dropping it would be a decision made on missing data.
 */
export function withinView(view: View, lat?: number | null, lng?: number | null): boolean {
  if (typeof lat !== "number" || typeof lng !== "number") return true;
  if (lat === 0 && lng === 0) return true;  // Null Island: never a real place
  return distanceKm({ lat: view.lat, lng: view.lng }, { lat, lng }) <= view.radiusKm;
}
