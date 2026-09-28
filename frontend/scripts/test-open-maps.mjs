// "Open in maps" has to open maps.
//
// All four of these used to build the same URL:
//
//   https://www.openstreetmap.org/?mlat=…&mlon=…#map=16/…
//
// which is a web page with a pin on it. On a phone that is a browser tab — not
// Apple Maps, not Google Maps — and there is no route in it. The button said
// "An der Kaart opmaachen" and produced a picture of a map.
//
//   node --experimental-strip-types scripts/test-open-maps.mjs

import { readFileSync } from "node:fs";

let failures = 0;
function check(name, actual, expected) {
  if (actual !== expected) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

import { mapsUrl } from "../src/utils/mapsUrl.ts";

const urlFor = (os, lat, lng, label) => mapsUrl(lat, lng, label, os);

const LAT = 49.9796, LNG = 5.9111;

// --- iOS: Apple Maps, and a route ----------------------------------------
const ios = urlFor("ios", LAT, LNG, "Spillplaatz op der Lou");
check("iOS goes to Apple Maps", ios.startsWith("https://maps.apple.com/"), true);
check("iOS asks for a destination, which is what makes it a route",
  ios.includes(`daddr=${LAT},${LNG}`), true);
check("iOS carries the name", ios.includes("Spillplaatz"), true);

// --- Android: the user's own maps app ------------------------------------
const android = urlFor("android", LAT, LNG, "Spillplaatz op der Lou");
check("Android uses the platform's geo scheme", android.startsWith("geo:"), true);
check("Android puts the point in the scheme itself",
  android.startsWith(`geo:${LAT},${LNG}`), true);
// The label sits in brackets after the point, as Android's geo: scheme wants.
// encodeURIComponent leaves parentheses alone, which is correct — they are
// part of the scheme's grammar, not part of the label.
check("Android names the pin", /\(Spillplaatz%20op%20der%20Lou\)/.test(android), true);
check("and the brackets stay brackets", android.includes("%28"), false);

// --- Web: a route, not a pin ---------------------------------------------
const web = urlFor("web", LAT, LNG);
check("the web gets directions, not a pin", web.includes("/directions"), true);
check("and not the old pin link", web.includes("mlat="), false);

// --- no label is not a broken URL ----------------------------------------
for (const os of ["ios", "android", "web"]) {
  const u = urlFor(os, LAT, LNG);
  check(`${os} survives a missing label`, u.includes("undefined") || u.includes("null"), false);
  check(`${os} still carries the coordinates`, u.includes(String(LAT)), true);
}

// --- nobody builds the old URL by hand any more ---------------------------
for (const file of [
  "app/event/[id].tsx",
  "app/detail/[id].tsx",
  "app/places.tsx",
  "app/(tabs)/explore.tsx",
]) {
  const s = readFileSync(file, "utf8");
  check(`${file} no longer hand-builds an openstreetmap pin link`,
    /openstreetmap\.org\/\?mlat/.test(s), false);
  check(`${file} goes through the helper`, /openMaps\(/.test(s), true);
}

console.log(failures === 0
  ? "  test-open-maps: all checks passed"
  : `  test-open-maps: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
