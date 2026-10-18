// Tapping an event has to open that event.
//
// Every way out of the Entdecken screen — the result list, the sheet that
// opens when several events sit on one spot, and a tap on a map pin — pushed
// `/detail/${e.id}`. That screen looks the id up with
//
//     PLACES.find((p) => p.id === Number(id))
//
// in the eight hard-coded demo records. `Number("5e2cf1ae-…")` is NaN, so it
// matched nothing and rendered "Not found". Not for one event: for every event,
// on every one of the three paths, for as long as the screen has shown live
// data.
//
// Two things hid it. The route was written as a plain template string with
// `as never` attached, which switches off expo-router's typed-route check —
// the very check the comment above detailHref() says is there to catch this.
// And the demo screen answers with a page rather than an error, so nothing in
// a log or a test ever said a word.
//
//   node --experimental-strip-types scripts/test-detail-routes.mjs

import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";

import { detailHref, eventHref } from "../src/utils/toPlace.ts";

let failures = 0;
function check(name, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

const UUID = "5e2cf1ae-c889-4868-ad74-113ed1c09a16";

check("a live event goes to the screen that fetches it", eventHref(UUID), `/event/${UUID}`);
check("a record with a real id goes there too",
  detailHref({ id: 42, sourceId: UUID }), `/event/${UUID}`);
check("a demo record still goes to the demo screen",
  detailHref({ id: 3, sourceId: undefined }), "/detail/3");

// The thing that actually broke: a real id reaching /detail/, where it is read
// with Number() and cannot match.
check("Number() of a real id is not a demo index", Number.isNaN(Number(UUID)), true);

// No screen may write either route by hand. One place knows the paths; that is
// what makes the typed-route check able to catch a typo.
const files = execSync('find app src -name "*.tsx"', { encoding: "utf8" })
  .split("\n").filter(Boolean);
for (const file of files) {
  const text = readFileSync(file, "utf8");
  if (file.startsWith("app/detail/")) continue;   // the screen itself
  check(`${file} does not write /detail/ by hand`, /`\/detail\/\$\{/.test(text), false);
  check(`${file} does not cast a route to never`, /as never\)/.test(text), false);
}

// Code only: the prose above eventHref() quotes the broken path on purpose,
// and a count that includes comments would make that explanation a failure.
const code = readFileSync("src/utils/toPlace.ts", "utf8")
  .split("\n")
  .filter((line) => !/^\s*(\*|\/\/|\/\*)/.test(line))
  .join("\n");
check("each route is written exactly once, and only here",
  (code.match(/`\/(event|detail)\/\$\{/g) ?? []).length, 2);

console.log(failures === 0
  ? "  test-detail-routes: all checks passed"
  : `  test-detail-routes: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
