// The map must not draw places the data does not have.
//
// 80.9 % of our events carry only a town name, so they are geocoded to that
// town's centre and hundreds land on an identical coordinate — 101 of them on
// one point in Esch-sur-Alzette. MarkerCluster's default answer at maximum
// zoom is `spiderfyOnMaxZoom`, which fans them into a ring: nine pins drawn
// around a village where there is one location.
//
// That is the same failure as an age of "0" or a price of "0.00 €" — a value
// the source never supplied, rendered as though it had been. This checks the
// ring stays gone and that what replaced it is actually wired up.
//
//   node --experimental-strip-types scripts/test-map-honesty.mjs

import { readFileSync } from "node:fs";

let failures = 0;
function check(name, actual, expected) {
  if (actual !== expected) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

const html = readFileSync("src/components/leafletHtml.ts", "utf8");

// --- the ring itself ------------------------------------------------------
check("spiderfying is off", /spiderfyOnMaxZoom:\s*false/.test(html), true);
check("and not merely absent, which would fall back to the default",
  /spiderfyOnMaxZoom/.test(html), true);

// The default click handler would zoom to bounds; for markers on one point
// that does nothing at all, so the cluster has to be handled by hand.
check("the cluster's own click handling is taken over",
  /zoomToBoundsOnClick:\s*false/.test(html), true);
check("a cluster click is handled", /cluster\.on\("clusterclick"/.test(html), true);

// --- one spot versus several close together -------------------------------
//
// Not every cluster is one coordinate: maxClusterRadius groups markers that
// are merely near each other on screen. Those must still zoom apart, or the
// map would stop being a map.
check("a cluster that is really one point is recognised",
  /function isOneSpot/.test(html), true);
check("clusters that are not one point still zoom",
  /if \(!isOneSpot\(bounds\)\)[\s\S]{0,160}fitBounds/.test(html), true);
check("and one point posts the ids instead",
  /type:\s*"clusterTap"/.test(html), true);

// The ids have to come from somewhere; a marker carries its own.
check("markers remember which event they are",
  /__watEventId\s*=\s*event\.id/.test(html), true);

// --- the bridge -----------------------------------------------------------
const bridge = readFileSync("src/components/LeafletMap.tsx", "utf8");
check("the bridge forwards clusterTap", /data\.type === "clusterTap"/.test(bridge), true);
check("and only forwards real string ids",
  /typeof id === "string"/.test(bridge), true);

// --- the listener must not hold yesterday's callbacks ---------------------
//
// The web bridge attaches its `message` listener once, on mount, with an empty
// dependency list — and a listener attached once keeps the closure it was made
// with. `onClusterTap` is rebuilt whenever the event list changes, so the
// listener held the very first one: the one that closed over an empty list.
// The map posted, the bridge received, the handler ran against nothing, and
// the sheet never opened. Every file looked right on its own.
check("the bridge reads its callbacks from a ref",
  /const handlers = useRef\(\{/.test(bridge), true);
check("and the ref is refreshed on every render",
  /handlers\.current = \{/.test(bridge), true);
for (const cb of ["onMarkerTap", "onClusterTap", "onReady"]) {
  check(`${cb} is called through the ref`,
    new RegExp(`handlers\\.current\\.${cb}\\?\\.\\(`).test(bridge), true);
}

// --- the screen -----------------------------------------------------------
const explore = readFileSync("app/(tabs)/explore.tsx", "utf8");
check("the screen takes the cluster tap", /onClusterTap=\{onClusterTap\}/.test(explore), true);
check("and shows the events as a list", /same-spot-sheet/.test(explore), true);

// A list that says nothing about why these are together would leave the
// reader to assume the app simply lost the addresses.
check("the list says why they share a spot",
  /sameSpotNote/.test(explore), true);

// --- the note exists in every language ------------------------------------
const strings = readFileSync("src/i18n/strings.ts", "utf8");
for (const key of ["eventsAtThisSpot", "sameSpotNote"]) {
  check(`${key} is defined`, new RegExp(`${key}:\\s*\\{`).test(strings), true);
  check(`${key} has Luxembourgish`,
    new RegExp(`${key}:\\s+"`).test(strings), true);
}

// --- the map carries places too -------------------------------------------
//
// It used to carry events alone, and events are the half of our data with the
// worse coordinates. Meanwhile 7,856 OpenStreetMap places sat unused — 1,383
// playgrounds, the picnic spots, the PLOMM Kannermusée — each with a real
// position. Zooming to a street showed an empty street: the tiles go to zoom
// 19, and there was nothing on them.
check("the map has a layer for places", /placeCluster/.test(html), true);
check("places are a separate group from events",
  /const placeCluster = L\.markerClusterGroup/.test(html), true);
check("and the map can be given places", /function setPlaces/.test(html), true);
check("a place pin can be told from an event pin",
  /wat-pin place/.test(html), true);

// Places have real coordinates, so zooming genuinely separates them — unlike
// events, where it cannot.
check("a cluster of places still zooms apart",
  /placeCluster[\s\S]{0,400}zoomToBoundsOnClick:\s*true/.test(html), true);

// The screen can only ask for the right places if it knows what is on screen.
check("the map reports where it is looking", /type:\s*"viewChanged"/.test(html), true);
check("and not on every pixel of a drag", /setTimeout\(\s*\(\)\s*=>\s*\{[\s\S]{0,400}viewChanged/.test(html), true);

check("the bridge forwards viewChanged", /data\.type === "viewChanged"/.test(bridge), true);
check("the bridge forwards placeTap", /data\.type === "placeTap"/.test(bridge), true);

check("the screen asks for places when the view settles",
  /onViewChanged=\{onViewChanged\}/.test(explore), true);
check("but not for the whole country at once",
  /PLACES_FROM_ZOOM/.test(explore), true);

// A slow answer for a view the reader has already left must not replace the
// pins for the one they are looking at.
check("a stale answer is dropped",
  /viewRef\.current !== view/.test(explore), true);

// The taxonomy ships translated labels; the raw OSM tag ("playground") is not
// a label, it is a key.
check("a pin says Spillplaz, not playground",
  /kindLabel\(p\.kind\)/.test(explore), true);
check("and says nothing at all for a tag we do not know",
  /if \(!entry\) return "";/.test(explore), true);

console.log(failures === 0
  ? "  test-map-honesty: all checks passed"
  : `  test-map-honesty: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
