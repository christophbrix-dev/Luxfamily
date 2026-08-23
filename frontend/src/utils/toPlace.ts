// Bridge between what the API returns and what the screens already render.
//
// Home, Saved, Calendar, Detail and Booking were written against `Place`, the
// shape of the eight hard-coded demo entries in src/data/places.ts. The API
// returns `ApiEventSummary`. Rather than rewrite five screens and AppCard, this
// maps one onto the other — the same data, in the shape the components expect.
//
// The two differ in naming (camelCase against snake_case) and in reach: the
// summary deliberately leaves out the long prose, which lives on the detail
// endpoint. Fields that only exist there come back empty here, which is honest:
// a card never showed them anyway.

import type { Canton, LocalizedString, Place } from "@/src/data/places";
import type { ApiEventSummary } from "@/src/utils/api";

const EMPTY: LocalizedString = { en: "", de: "", fr: "" };

/** "2-10", or "Alle Altersgruppen" when the range covers everything. */
function ageLabel(min: number, max: number): string {
  if (min <= 0 && max >= 99) return "0-99";
  return `${min}-${max}`;
}

/**
 * One API event in the shape the existing screens render.
 *
 * `distanceKm` is deliberately left undefined. The demo entries carried a fixed
 * number each — "2.4 km" was written into the file, not measured — and the app
 * has no location permission to compute a real one. Showing "0.0 km" on every
 * card would look like a measurement and be a lie; the components hide the
 * pill when the value is missing.
 */
export function toPlace(ev: ApiEventSummary): Place {
  return {
    // Place.id is numeric because the demo entries were numbered 1-8. Real ids
    // are uuids, so the numeric field carries a stable hash and `sourceId`
    // keeps the value routing actually needs.
    id: hashId(ev.id),
    sourceId: ev.id,
    title: ev.title,
    short: ev.short,
    type: ev.type,
    age: ageLabel(ev.age_min, ev.age_max),
    ageMin: ev.age_min,
    ageMax: ev.age_max,
    town: ev.town,
    canton: ev.canton as Canton,
    category: ev.category,
    image: ev.image,
    time: ev.time,
    priceAdult: ev.price_adult,
    priceChild: ev.price_child,
    lat: ev.lat,
    lng: ev.lng,
    rating: ev.rating,
    wheelchair: ev.accessibility_wheelchair,
    sensoryFriendly: ev.sensory_friendly,
    freeParking: ev.free_parking,

    // Detail-only. The list endpoint omits them on purpose — carrying them for
    // every row is what made the payload roughly three times bigger.
    date: EMPTY,
    weatherFit: EMPTY,
    priceLabel: EMPTY,
    accessibility: EMPTY,
    description: EMPTY,
    bookable: false,
  };
}

export function toPlaces(events: readonly ApiEventSummary[]): Place[] {
  return events.map(toPlace);
}

/** Stable small integer from a uuid, so React keys stay put across reloads. */
function hashId(id: string): number {
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}
