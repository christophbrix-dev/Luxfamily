// An event is over when it ends, not the day after it begins.
//
// `upcoming` on the backend, and the sort and grouping here, both read
// `start_date` and nothing else. For a concert that is right. For the 135
// multi-day entries it is not, and the ones it got wrong were the ones a
// family actually wants: "Mount vum Bongert 2026" runs the whole of October,
// the Actionbound trail in Reisdorf likewise, "Rollblitzverleih" from the end
// of August into November. Nine events were running on 13 October 2026 and the
// app showed none of them.
//
// The second rule checked here is the one about not knowing. 299 of 1,435
// events carry a start date and no end, so "is it still on?" has no answer in
// the data. The card says when such an entry started and claims nothing more —
// "läuft noch" on something that may well be over is the kind of confident
// wrong answer this project keeps finding.
//
//   node --experimental-strip-types scripts/test-event-dates.mjs

import { readFileSync } from "node:fs";

// eventDates.ts imports nothing, which is what makes it runnable from plain
// node — the same shape as eventQuery.ts, mapsUrl.ts and accents.ts.
import { boxDate, dateNote, relevantFrom } from "../src/utils/eventDates.ts";

let failures = 0;
function check(name, actual, expected) {
  const a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a !== e) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        expected ${e}, got ${a}`);
  }
}

const TODAY = "2026-10-13";

// ---------------------------------------------------------------------------
// relevantFrom — the sort and grouping key
// ---------------------------------------------------------------------------

check("a future event is relevant from its start date",
  relevantFrom("2026-10-20", TODAY), "2026-10-20");
check("today's event is relevant from today",
  relevantFrom(TODAY, TODAY), TODAY);
check("something running since August is relevant from today, not August",
  relevantFrom("2026-08-31", TODAY), TODAY);
check("which is what keeps it out of an 'August' heading in a list of what's on",
  relevantFrom("2026-08-31", TODAY).slice(0, 7), "2026-10");

// ---------------------------------------------------------------------------
// dateNote — what the card may claim
// ---------------------------------------------------------------------------

check("a future event needs no note",
  dateNote({ start_date: "2026-10-20", end_date: "2026-10-20" }, TODAY),
  { kind: "none" });

check("an event starting today needs no note",
  dateNote({ start_date: TODAY, end_date: null }, TODAY),
  { kind: "none" });

check("one that began earlier and states an end that has not passed is running",
  dateNote({ start_date: "2026-10-01", end_date: "2026-10-31" }, TODAY),
  { kind: "runsUntil", date: "2026-10-31" });

check("a run ending today still counts as running today",
  dateNote({ start_date: "2026-10-01", end_date: TODAY }, TODAY),
  { kind: "runsUntil", date: TODAY });

check("one that began earlier with no stated end only says when it began",
  dateNote({ start_date: "2026-10-11", end_date: null }, TODAY),
  { kind: "startedOn", date: "2026-10-11" });

check("a missing end_date is the same as a null one",
  dateNote({ start_date: "2026-10-11" }, TODAY),
  { kind: "startedOn", date: "2026-10-11" });

check("an end that has passed is not a claim that it is running",
  dateNote({ start_date: "2026-10-01", end_date: "2026-10-05" }, TODAY),
  { kind: "startedOn", date: "2026-10-01" });

// ---------------------------------------------------------------------------
// boxDate — the big day/month on the left of the card
// ---------------------------------------------------------------------------

check("a future event shows its own date", boxDate({ start_date: "2026-10-20" }, TODAY), "2026-10-20");
check("a running event shows today, because today is when you can go",
  boxDate({ start_date: "2026-08-31", end_date: "2026-10-30" }, TODAY), TODAY);

// ---------------------------------------------------------------------------
// The screen has to use them, or none of the above reaches anybody
// ---------------------------------------------------------------------------

const screen = readFileSync("app/(tabs)/events.tsx", "utf8");
check("the list sorts by relevance, not by raw start date",
  /relevantFrom\(/.test(screen), true);
check("and no longer compares start_date directly when ordering",
  /a\.start_date\.localeCompare\(b\.start_date\)/.test(screen), false);
check("the month heading is built from the relevance key",
  /new Date\(relevantFrom\(/.test(screen), true);
check("and no longer from the raw start date, which opened an 'August' heading",
  /new Date\(e\.start_date\)/.test(screen), false);
check("the card asks for a note", /dateNote\(/.test(screen), true);
check("and the date box uses boxDate", /boxDate\(/.test(screen), true);

// Both notes must be sayable in every language the app speaks.
const strings = readFileSync("src/i18n/strings.ts", "utf8");
for (const key of ["runsUntil", "startedOn"]) {
  check(`${key} is defined`, new RegExp(`${key}:\\s*\\{`).test(strings), true);
  check(`${key} has Luxembourgish`, new RegExp(`\\n\\s+${key}:\\s+"`).test(strings), true);
}

console.log(failures === 0
  ? "  test-event-dates: all checks passed"
  : `  test-event-dates: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
