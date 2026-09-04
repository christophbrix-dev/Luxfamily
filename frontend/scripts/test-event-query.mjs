// Tests for turning the filter sheet into a question the server can answer.
//
// All of this used to run in the app, over whatever had been downloaded — 200
// events out of 401. Choosing "Spillplaz" searched 200 rows and returned
// whatever happened to be among them.
//
// The date chip was worse than incomplete: it was drawn, it counted towards
// the "active filters" badge, and it was never applied to anything. Picking
// "This weekend" did nothing at all except light up a number.
//
//   node --experimental-strip-types scripts/test-event-query.mjs

import { readFileSync } from "node:fs";

import { ageWindow, buildEventQuery, dateWindow } from "../src/utils/eventQuery.ts";

let failures = 0;
function check(name, actual, expected) {
  if (actual !== expected) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

// --- nothing asked, nothing sent -----------------------------------------
check("no filters is no query string", buildEventQuery(), "");
check("empty object likewise", buildEventQuery({}), "");
check('"All" is not a filter', buildEventQuery({ type: "All" }), "");
check("an empty category list is not a filter", buildEventQuery({ category: [] }), "");
check("a blank search box is not a filter", buildEventQuery({ q: "   " }), "");

// --- the switches only ever narrow ---------------------------------------
check("a switch that is on is sent",
  buildEventQuery({ wheelchair: true }), "?wheelchair=true");
check("a switch that is off is left out entirely",
  buildEventQuery({ wheelchair: false, sensory: false, freeParking: false }), "");

// --- categories are a list -----------------------------------------------
check("one category",
  buildEventQuery({ category: ["Playgrounds"] }), "?category=Playgrounds");
check("several categories repeat the parameter",
  buildEventQuery({ category: ["Playgrounds", "Nature"] }),
  "?category=Playgrounds&category=Nature");

// --- ages ----------------------------------------------------------------
check("an age band becomes a range", JSON.stringify(ageWindow("4-6")),
  JSON.stringify({ ageMin: 4, ageMax: 6 }));
check('"All" is no range', JSON.stringify(ageWindow("All")), "{}");
check("nonsense is no range", JSON.stringify(ageWindow("junge Leute")), "{}");
check("the range reaches the query string",
  buildEventQuery(ageWindow("0-3")), "?age_min=0&age_max=3");

// --- the date chip, which never did anything -----------------------------
const wednesday = new Date(2026, 8, 2);           // 2 September 2026, a Wednesday
check("today is one day", JSON.stringify(dateWindow("Today", wednesday)),
  JSON.stringify({ dateFrom: "2026-09-02", dateTo: "2026-09-02" }));
check("the coming weekend from a Wednesday",
  JSON.stringify(dateWindow("This weekend", wednesday)),
  JSON.stringify({ dateFrom: "2026-09-05", dateTo: "2026-09-06" }));
check("the next seven days",
  JSON.stringify(dateWindow("Next 7 days", wednesday)),
  JSON.stringify({ dateFrom: "2026-09-02", dateTo: "2026-09-09" }));
check('"Anytime" constrains nothing', JSON.stringify(dateWindow("Anytime", wednesday)), "{}");

// Asked on the weekend itself, "this weekend" has to mean this one — somebody
// looking for Saturday plans on Saturday morning does not mean next week.
const saturday = new Date(2026, 8, 5);
check("asked on Saturday, the weekend is today",
  JSON.stringify(dateWindow("This weekend", saturday)),
  JSON.stringify({ dateFrom: "2026-09-05", dateTo: "2026-09-06" }));

const sunday = new Date(2026, 8, 6);
check("asked on Sunday, the weekend is today and not in six days",
  JSON.stringify(dateWindow("This weekend", sunday)),
  JSON.stringify({ dateFrom: "2026-09-06", dateTo: "2026-09-06" }));

// The date has to be the local calendar day. `toISOString` would roll over to
// tomorrow for anyone east of Greenwich in the evening — which is Luxembourg,
// every evening.
const lateEvening = new Date(2026, 8, 2, 23, 30);
check("an evening does not become tomorrow",
  dateWindow("Today", lateEvening).dateFrom, "2026-09-02");

// --- everything together --------------------------------------------------
const full = buildEventQuery({
  type: "Indoor",
  category: ["Workshops"],
  wheelchair: true,
  ...ageWindow("4-6"),
  ...dateWindow("Today", wednesday),
  q: "Kajak",
});
for (const part of ["type=Indoor", "category=Workshops", "wheelchair=true",
                    "age_min=4", "age_max=6", "date_from=2026-09-02", "q=Kajak"]) {
  check(`the combined query carries ${part}`, full.includes(part), true);
}
check("and starts with a single question mark", full.startsWith("?") && !full.slice(1).includes("?"), true);

// --- the app no longer sieves what the server already sieved --------------
//
// Only the filter predicate is examined, not the whole file: `filters.category`
// still appears in the badge that counts how many filters are active, and
// counting is not filtering. Checking the file as a whole confused the two.
const explore = readFileSync("app/(tabs)/explore.tsx", "utf8")
  .replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
const start = explore.indexOf("const filtered = useMemo");
const predicate = explore.slice(start, explore.indexOf("}, [", start));
check("the predicate was found at all", start > 0 && predicate.length > 40, true);

for (const [what, pattern] of [
  ["category", /filters\.category/],
  ["age", /filters\.age/],
  ["type", /filters\.type/],
  ["the family-needs switches", /filters\.(wheelchair|sensoryFriendly|freeParking)/],
]) {
  check(`the predicate no longer re-applies ${what}`, pattern.test(predicate), false);
}
check("but it still applies the canton, because the pill counts need it",
  /canton && e\.canton !== canton/.test(predicate), true);
check("and the search box, which would cost a request per keystroke",
  /hay\.includes\(q\)/.test(predicate), true);

console.log(failures === 0
  ? "  test-event-query: all checks passed"
  : `  test-event-query: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
