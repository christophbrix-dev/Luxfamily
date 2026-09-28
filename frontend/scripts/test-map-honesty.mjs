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

// --- routes are drawn, not pinned -----------------------------------------
//
// 865 of the places are hiking and cycle trails. A pin in the middle of one
// says "this is here", and a route is not anywhere in particular: the
// Sauer-Radweg runs through Echternach and 40 km from Esch at the same time.
// Measured against the real data, a pin in the middle of it would have told
// somebody in Echternach "8.3 km" for a trail 100 metres away.
check("routes get their own layer", /const routeLayer = L\.layerGroup/.test(html), true);
check("and are drawn as a line", /L\.polyline\(/.test(html), true);
check("a place with a shape is not also pinned",
  /Array\.isArray\(place\.pathParts\) && place\.pathParts\.length\) return;/.test(html), true);
check("a line can be tapped like a pin", /line\.bindPopup/.test(html), true);

check("the bridge carries route shapes", /pathParts\?: number\[\]\[\]\[\]/.test(bridge), true);

// A route has no coordinate at all — the old filter would have dropped it
// before it ever reached the map.
check("the screen keeps places that have a shape but no point",
  /p\.lat !== null && p\.lng !== null\) \|\| p\.path_parts\?\.length/.test(explore), true);
// Was `geometry: true` until the layer switches arrived; now it is asked for
// only when something draws it. The check below covers the rest.
check("and asks the server for the shapes when they are drawn",
  /geometry: wantsRoutes/.test(explore), true);

// Route shapes were 70 KB of a 331 KB answer for 39 rows out of 300. Only the
// map draws them, so only the map should pay for them.
const api = readFileSync("src/utils/api.ts", "utf8");
check("geometry is off unless asked for",
  /if \(opts\.geometry\) q\.set\("geometry", "true"\)/.test(api), true);

// --- what the map draws is the reader's choice ----------------------------
//
// The map carries four things now, and 4,772 of the 7,856 places are nature
// and picnic spots. Somebody looking for a bike ride does not want the
// country's every bench drawn over it.
check("the screen has layer switches", /const \[layers, setLayers\]/.test(explore), true);
check("all four are switchable",
  /"events", "places", "hiking", "cycling"/.test(explore), true);

// Sieving happens in the screen, so flipping a switch redraws without a round
// trip — and the request is made once for every combination.
check("routes are sorted by kind, not by group",
  /kind === "cycle_route"/.test(explore) && /kind === "hiking_route"/.test(explore), true);

// Route shapes were 70 KB of a 331 KB answer. With both route layers off,
// nobody draws them.
check("geometry is only asked for when a route layer is on",
  /geometry: wantsRoutes/.test(explore), true);
check("and wantsRoutes is exactly that",
  /const wantsRoutes = layers\.hiking \|\| layers\.cycling/.test(explore), true);

// A switch is not a new viewport, so the map's own moveend never fires.
check("flipping a switch redraws",
  /if \(viewRef\.current\) void onViewChanged\(viewRef\.current\)/.test(explore), true);
check("and the event layer answers to its switch",
  /setEvents\(layers\.events \? markers : \[\]\)/.test(explore), true);

// The choice is remembered per reader. Stored as the names that are on, so a
// layer added later does not arrive switched off for everyone who was here.
check("the choice is kept", /storage\.setItem\(\s*LAYERS_KEY/.test(explore), true);
check("as names rather than a fixed shape",
  /ALL_LAYERS\.filter\(\(k\) => next\[k\]\)\.join\(","\)/.test(explore), true);

// Labels, in every language the app speaks.
for (const key of ["onTheMap", "hikingTrails", "cycleRoutes"]) {
  check(`${key} is defined`, new RegExp(`${key}:\\s*\\{`).test(strings), true);
  check(`${key} has Luxembourgish`, new RegExp(`${key}:\\s+"`).test(strings), true);
}

console.log(failures === 0
  ? "  test-map-honesty: all checks passed"
  : `  test-map-honesty: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
