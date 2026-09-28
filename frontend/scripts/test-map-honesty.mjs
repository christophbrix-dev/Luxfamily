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

console.log(failures === 0
  ? "  test-map-honesty: all checks passed"
  : `  test-map-honesty: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
