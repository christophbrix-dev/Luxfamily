// The list follows the map.
//
// The places layer has done this since it was written: pan, and the pins for
// the new view are fetched. The event list did not — one request for the whole
// country, narrowed afterwards only by canton and search box. So zooming to
// Esch-sur-Alzette left Vianden at the top of the list, sixty kilometres away
// and nowhere on the screen.
//
// The two things worth guarding here are both about *not* filtering:
//
//   - not at country zoom, where the circle does not even cover Luxembourg and
//     filtering would silently drop Clervaux from a list nobody narrowed;
//   - not an entry whose coordinates we do not have, because that would be a
//     decision taken on missing data.
//
//   node --experimental-strip-types scripts/test-viewport.mjs

import { readFileSync } from "node:fs";

import { FOLLOW_FROM_ZOOM, distanceKm, followsView, withinView } from "../src/utils/viewport.ts";

let failures = 0;
function check(name, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

// Real places, so a reader can check the numbers against a map.
const ESCH     = { lat: 49.4958, lng: 5.9806 };
const VIANDEN  = { lat: 49.9353, lng: 6.2086 };
const CITY     = { lat: 49.6116, lng: 6.1319 };
const CLERVAUX = { lat: 50.0547, lng: 6.0286 };

// --- the distance itself ----------------------------------------------------
// Cross-checked against the law of cosines rather than taken on trust; an
// earlier guess in this project ("Luxembourg–Esch is about 15 km") was wrong
// by two kilometres and nothing complained.
const lawOfCosines = (a, b) => {
  const r = Math.PI / 180, R = 6371;
  return R * Math.acos(
    Math.sin(a.lat * r) * Math.sin(b.lat * r) +
    Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.cos((b.lng - a.lng) * r));
};
for (const [name, a, b] of [["Esch→City", ESCH, CITY], ["City→Vianden", CITY, VIANDEN]]) {
  const mine = distanceKm(a, b), theirs = lawOfCosines(a, b);
  check(`${name}: haversine agrees with the law of cosines`,
    Math.abs(mine - theirs) < 0.01, true);
}

// --- when the list follows at all -------------------------------------------
check("the country view does not filter", followsView({ ...CITY, zoom: 9, radiusKm: 40 }), false);
check("nor does a missing view", followsView(null), false);
check("a region view does", followsView({ ...ESCH, zoom: FOLLOW_FROM_ZOOM, radiusKm: 12 }), true);

// --- what is inside it ------------------------------------------------------
const eschView = { ...ESCH, zoom: 12, radiusKm: 8 };
check("Esch is in a view centred on Esch", withinView(eschView, ESCH.lat, ESCH.lng), true);
check("the capital is not, 17 km away", withinView(eschView, CITY.lat, CITY.lng), false);
check("Vianden is certainly not — this is the complaint",
  withinView(eschView, VIANDEN.lat, VIANDEN.lng), false);
check("Clervaux is not either", withinView(eschView, CLERVAUX.lat, CLERVAUX.lng), false);

const wide = { ...CITY, zoom: 10, radiusKm: 60 };
check("a wide region view keeps Esch", withinView(wide, ESCH.lat, ESCH.lng), true);
check("and Vianden", withinView(wide, VIANDEN.lat, VIANDEN.lng), true);

// --- what we refuse to decide ----------------------------------------------
check("an entry without coordinates stays", withinView(eschView, null, null), true);
check("so does one with only half of them", withinView(eschView, 49.5, undefined), true);
check("Null Island is not a location and is not used to drop anything",
  withinView(eschView, 0, 0), true);

// --- it is actually wired in ------------------------------------------------
const screen = readFileSync("app/(tabs)/explore.tsx", "utf8");
check("the list applies it", /followsView\(view\) && !withinView\(view, e\.lat, e\.lng\)/.test(screen), true);
check("the view is state, not only a ref",
  /const \[view, setView\] = useState<MapView \| null>\(null\)/.test(screen), true);
check("and it is set when the map moves", /setView\(view\);/.test(screen), true);
check("the filter recomputes when the view changes",
  /\[events, canton, query, lang, view\]/.test(screen), true);
check("the count says when it is following the map", /t\("inThisView", lang\)/.test(screen), true);

const strings = readFileSync("src/i18n/strings.ts", "utf8");
check("inThisView is defined", /inThisView:\s*\{/.test(strings), true);
check("inThisView has Luxembourgish", /\n\s+inThisView:\s+"/.test(strings), true);

// One haversine, not two: useUserLocation now re-exports this one.
const hook = readFileSync("src/hooks/useUserLocation.ts", "utf8");
check("there is only one distance formula",
  /export \{ distanceKm \} from "@\/src\/utils\/viewport"/.test(hook), true);
check("and the old copy is gone", /Math\.asin\(Math\.sqrt\(h\)\)/.test(hook), false);

console.log(failures === 0
  ? "  test-viewport: all checks passed"
  : `  test-viewport: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
