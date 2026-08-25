// Tests for the opening-hours parser.
//
// This one decides whether the app tells someone a place is open. Get it
// wrong and they drive there and find a locked door — which is the exact
// problem the app exists to solve, so it is worth its own checks even though
// the frontend has no test runner.
//
// Node strips the TypeScript itself, so there is nothing to install.
//
//   node --experimental-strip-types scripts/test-opening-hours.mjs

import { isOpenAt, openLabel } from "../src/utils/openingHours.ts";

let failures = 0;

function check(name, actual, expected) {
  const ok = actual === expected;
  if (!ok) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
  return ok;
}

// 2026-08-25 is a Tuesday, 2026-08-30 a Sunday.
const tueAfternoon = new Date("2026-08-25T14:30:00");
const tueNight = new Date("2026-08-25T03:00:00");
const tueEarly = new Date("2026-08-25T08:00:00");
const sunMorning = new Date("2026-08-30T11:00:00");

// --- always open --------------------------------------------------------
check("24/7 at 3am", isOpenAt("24/7", tueNight), "open");
check("24/7 on Sunday", isOpenAt("24/7", sunMorning), "open");

// --- a plain weekday range ---------------------------------------------
check("inside the range", isOpenAt("Mo-Sa 09:00-18:00", tueAfternoon), "open");
check("before opening", isOpenAt("Mo-Sa 09:00-18:00", tueEarly), "closed");
check("wrong day", isOpenAt("Mo-Sa 09:00-18:00", sunMorning), "closed");

// Boundaries: open at the opening minute, shut at the closing one. A place
// that closes at 18:00 is not open at 18:00.
check("at opening time", isOpenAt("Mo-Su 14:30-18:00", tueAfternoon), "open");
check("at closing time", isOpenAt("Mo-Su 09:00-14:30", tueAfternoon), "closed");

// --- lunch breaks -------------------------------------------------------
check("in the morning half", isOpenAt("Mo-Fr 08:00-12:00,14:00-18:00", tueEarly), "open");
check("during the break", isOpenAt("Mo-Fr 08:00-12:00,14:00-13:00", new Date("2026-08-25T13:00:00")), "closed");
check("in the afternoon half", isOpenAt("Mo-Fr 08:00-12:00,14:00-18:00", tueAfternoon), "open");

// --- exceptions win over the rule they follow ---------------------------
check("Su off closes Sunday", isOpenAt("Mo-Su 10:00-18:00; Su off", sunMorning), "closed");
check("Su off leaves Tuesday alone", isOpenAt("Mo-Su 10:00-18:00; Su off", tueAfternoon), "open");
check("closed reads like off", isOpenAt("Mo-Su 10:00-18:00; Tu closed", tueAfternoon), "closed");

// --- past midnight ------------------------------------------------------
check("after midnight", isOpenAt("Mo-Su 22:00-04:00", tueNight), "open");
check("mid-afternoon is not", isOpenAt("Mo-Su 22:00-04:00", tueAfternoon), "closed");

// --- day lists and wrapping ranges --------------------------------------
check("day list includes Tuesday", isOpenAt("Mo,Tu,We 09:00-18:00", tueAfternoon), "open");
check("day list excludes Sunday", isOpenAt("Mo,Tu,We 09:00-18:00", sunMorning), "closed");
check("Fr-Mo wraps the weekend", isOpenAt("Fr-Mo 09:00-18:00", sunMorning), "open");
check("Fr-Mo skips Tuesday", isOpenAt("Fr-Mo 09:00-18:00", tueAfternoon), "closed");

// --- times without a day mean every day ---------------------------------
check("bare range on Tuesday", isOpenAt("09:00-18:00", tueAfternoon), "open");
check("bare range on Sunday", isOpenAt("09:00-18:00", sunMorning), "open");

// --- what it refuses to answer ------------------------------------------
// Everything here can flip the answer on a given day. Saying "open" on a
// guess is worse than saying nothing, so these stay unknown.
for (const [name, value] of [
  ["empty", ""],
  ["missing", null],
  ["free text", "by appointment"],
  ["free text in French", "Sur rendez-vous"],
  ["public holidays", "Mo-Sa 10:00-18:00; PH off"],
  ["school holidays", "Mo-Fr 09:00-16:00; SH 10:00-14:00"],
  ["a season", "Apr 1-Oct 31 09:00-22:00"],
  ["sunset", "Mo-Su sunrise-sunset"],
  ["a year", "2026 Mo-Fr 09:00-17:00"],
  ["nonsense", "???"],
  ["a bad day name", "Xy-Fr 09:00-18:00"],
  ["a bad time", "Mo-Fr 25:00-99:00"],
]) {
  check(`unknown: ${name}`, isOpenAt(value, tueAfternoon), "unknown");
}

// --- the label ----------------------------------------------------------
check("German open", openLabel("24/7", "de", tueAfternoon), "Jetzt geöffnet");
check("Luxembourgish open", openLabel("24/7", "lb", tueAfternoon), "Elo op");
check("German closed", openLabel("Mo-Fr 09:00-12:00", "de", tueAfternoon), "Geschlossen");
check("no label when unsure", openLabel("by appointment", "de", tueAfternoon), null);

// --- real values from the Luxembourg extract ----------------------------
// Spot checks against strings that actually occur, not invented ones.
check("Parc Merveilleux", isOpenAt("Mo-Su 09:30-19:00", tueAfternoon), "open");
check("a shop on Sunday", isOpenAt("Mo-Sa 09:00-18:00", sunMorning), "closed");
check("split office hours", isOpenAt("Mo-Fr 08:00-10:00,16:00-18:00", tueAfternoon), "closed");
check("an open-ended range", isOpenAt("Mo-Su 08:00-18:00+", tueAfternoon), "unknown");

const total = 41;
if (failures) {
  console.log(`\n  ${failures} of ${total} checks failed`);
  process.exit(1);
}
console.log(`  opening hours: ${total} checks passed`);
