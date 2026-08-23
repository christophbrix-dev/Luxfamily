// Reports how much of the app speaks Luxembourgish.
//
// `lb` is optional in the type while the translations are being written, which
// means nothing complains when a text has none. This puts the number in front
// of us on every CI run, so "optional for now" does not quietly become
// "forgotten".
//
// It never fails the build — a missing translation is work in progress, not a
// broken commit. When coverage reaches 100%, make LocalizedString require `lb`
// again and the type takes over from this script.
//
//   node scripts/lb-coverage.mjs

import { readFileSync } from "node:fs";

const strings = readFileSync(new URL("../src/i18n/strings.ts", import.meta.url), "utf8");
const places = readFileSync(new URL("../src/data/places.ts", import.meta.url), "utf8");

/** Interface strings live in a separate LB_OVERRIDES map, not inline. */
function interfaceCoverage() {
  const dict = strings.split("export const STRINGS: Dict = {")[1]?.split("\n};")[0] ?? "";
  const keys = [...dict.matchAll(/^\s{2}(\w+):\s*\{/gm)].map((m) => m[1]);

  const overlay = strings.split("const LB_OVERRIDES: Record<string, string> = {")[1]
    ?.split("\n};")[0] ?? "";
  const translated = new Set([...overlay.matchAll(/^\s*(\w+):\s*"/gm)].map((m) => m[1]));

  return { total: keys.length, done: keys.filter((k) => translated.has(k)).length };
}

/** Place texts carry `lb` inline on the record. */
function placeCoverage() {
  const objects = [...places.matchAll(/\{[^{}]*?\ben:\s*"[^{}]*?\}/gs)].map((m) => m[0]);
  return {
    total: objects.length,
    done: objects.filter((o) => /\blb:\s*"/.test(o)).length,
  };
}

const ui = interfaceCoverage();
const pl = placeCoverage();
const total = ui.total + pl.total;
const done = ui.done + pl.done;
const pct = total ? Math.round((done / total) * 100) : 0;

console.log("Lëtzebuergesch coverage");
console.log(`  interface strings  ${ui.done}/${ui.total}`);
console.log(`  place texts        ${pl.done}/${pl.total}`);
console.log(`  total              ${done}/${total}  (${pct}%)`);

if (done < total) {
  console.log(`\n  ${total - done} still to translate — see translations/lb.csv`);
} else {
  console.log("\n  Complete. Make LocalizedString require `lb` again:");
  console.log("  src/data/places.ts -> Record<Lang, string>");
}
