// Every accent must carry its own text.
//
// `primary` was #10B981 for as long as the app existed. Measured against white
// it is 2.54 : 1, and WCAG AA asks 4.5 : 1 for body text — so every green
// button in the app, "Resultater weisen" included, had a label below the line.
// In dark mode white on #34D399 is 1.92 : 1. Nobody noticed because nobody
// measured; the colour looked fine to the person who chose it.
//
// Now that readers can choose an accent, that mistake could be made eight
// times over. So the shades are derived rather than typed, and this checks
// every one of them. It fails the build, unlike the Luxembourgish report:
// a missing translation is work in progress, an unreadable button is a defect.
//
//   node --experimental-strip-types scripts/test-contrast.mjs

import { readFileSync } from "node:fs";

// accents.ts imports nothing, which is what makes it testable from plain node
// — the same reason eventQuery.ts and mapsUrl.ts are shaped that way. theme.ts
// does import it, so theme.ts is checked as text further down rather than run.
import { ACCENTS, DEFAULT_ACCENT, accentById, contrast, hsl, shadesFor, DARK_SURFACE, LIGHT_SURFACE }
  from "../src/accents.ts";

let failures = 0;
function check(name, actual, expected) {
  if (actual !== expected) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}
function atLeast(name, value, floor) {
  if (!(value >= floor)) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        ${value.toFixed(2)} : 1, needs ${floor} : 1`);
  }
}

// --- the arithmetic itself ------------------------------------------------
//
// If hsl() or contrast() were wrong, every check below would agree with them
// and pass. So they are pinned to values that can be verified by hand.
check("hsl is a hex string", /^#[0-9A-F]{6}$/.test(hsl(138, 50, 70)), true);
check("saturation 0 is grey", hsl(138, 50, 0), "#808080");
check("lightness 100 is white", hsl(138, 100, 70), "#FFFFFF");
check("lightness 0 is black", hsl(138, 0, 70), "#000000");
atLeast("white on black is 21 : 1", contrast("#FFFFFF", "#000000"), 20.9);
check("a colour against itself is 1 : 1",
  Math.round(contrast("#168838", "#168838") * 100) / 100, 1);

// The old value, so the number this whole change exists for is written down.
atLeast("the old #10B981 really was that bad", 2.6 - contrast("#FFFFFF", "#10B981"), 0);

// --- every accent, both modes --------------------------------------------
for (const accent of ACCENTS) {
  const light = shadesFor(accent.hue, "light");
  const dark  = shadesFor(accent.hue, "dark");

  atLeast(`${accent.id}: white on the light button`,
    contrast("#FFFFFF", light.primary), 4.5);
  atLeast(`${accent.id}: accent text on a white card`,
    contrast(light.primaryDark, LIGHT_SURFACE), 7.0);
  // Two thresholds, because two things sit on a badge.
  //
  // Text takes primaryDark — the 7 : 1 shade — and must clear 4.5 : 1. The
  // first version of this test asked that of `primary` and failed all eight
  // accents, which was the test being wrong rather than the colours: `primary`
  // is chosen to be exactly 4.5 : 1 against pure white, so on any tinted
  // ground it is necessarily below that. No badge colour could have fixed it.
  //
  // `primary` still appears on a badge, but as an icon — the avatar, the hero
  // circle, the header badge — and a graphic needs 3 : 1, not 4.5 : 1.
  atLeast(`${accent.id}: badge text on its badge`,
    contrast(light.primaryDark, light.primaryLight), 4.5);
  atLeast(`${accent.id}: a badge icon on its badge`,
    contrast(light.primary, light.primaryLight), 3.0);

  atLeast(`${accent.id}: accent on the dark surface`,
    contrast(dark.primary, DARK_SURFACE), 4.5);
  atLeast(`${accent.id}: dark badge text on its badge`,
    contrast(dark.primary, dark.primaryLight), 4.5);
  atLeast(`${accent.id}: dark badge icon on its badge`,
    contrast(dark.primary, dark.primaryLight), 3.0);

  // A dark-mode button is filled with the accent and takes dark text, not
  // white — the same way the app already draws chips on dark.
  atLeast(`${accent.id}: dark text on the dark button`,
    contrast("#0B1120", dark.primary), 4.5);
}

// --- how theme.ts composes them -------------------------------------------
//
// Checked as text: theme.ts pulls in accents.ts, so running it here would need
// the app's module resolution. What matters is the shape of the composition,
// and that is visible in the source.
const theme = readFileSync("src/theme.ts", "utf8");

check("the palette is built from an accent",
  /export function paletteFor\(accentId: string, mode: "light" \| "dark"\): Palette/.test(theme), true);
check("the neutrals are separate from the accent",
  /type Neutrals = Omit<Palette, "primary" \| "primaryDark" \| "primaryLight">/.test(theme), true);
check("and the accent fills only those three",
  /\{ \.\.\.neutrals, \.\.\.shadesFor\(hue, mode\) \}/.test(theme), true);

// The semantic colours are in the neutrals, so no accent can carry them along.
// If red could move, the confirm button and the error message would end up the
// same colour.
for (const token of ["red", "amber", "amberSoft", "background", "surface", "textPrimary"]) {
  check(`${token} is a neutral, not an accent`,
    new RegExp(`^\\s*${token}:`, "m").test(theme), true);
}
check("the old emerald literal is gone from the palettes",
  /primary:\s*"#10B981"/.test(theme), false);

// The two static exports still exist — ten files import them — and are now
// built from the default accent rather than from the failing literal.
check("LIGHT_PALETTE comes from the builder",
  /export const LIGHT_PALETTE: Palette = paletteFor\(DEFAULT_ACCENT, "light"\)/.test(theme), true);
check("DARK_PALETTE too",
  /export const DARK_PALETTE: Palette = paletteFor\(DEFAULT_ACCENT, "dark"\)/.test(theme), true);

// --- the default ----------------------------------------------------------
check("the default is in the list", ACCENTS.some((a) => a.id === DEFAULT_ACCENT), true);
check("the default is the warmer green", DEFAULT_ACCENT, "meadow");
check("an unknown id falls back rather than crashing",
  accentById("no-such-accent").id, DEFAULT_ACCENT);

// --- the picker, where the choice is made ---------------------------------
//
// A row of dots is a guess: nobody can tell from a 24-pixel circle what a
// screen will look like. The preview is a real card and a real button in the
// colour under the finger, which is where a colour either works or does not.
const picker = readFileSync("src/components/AccentPicker.tsx", "utf8");

check("the picker previews a card and a button",
  /previewCard/.test(picker) && /previewBtn/.test(picker), true);
check("in the mode the reader is actually in",
  /paletteFor\(accent, effective\)/.test(picker), true);
check("badge text uses the darker shade, as the thresholds require",
  /color: preview\.primaryDark/.test(picker), true);
check("and a dark-mode button takes dark text, not white",
  /effective === "dark" \? "#0B1120" : "#FFFFFF"/.test(picker), true);

// One component in both places, or changing the colour later would feel like
// a different decision from making it the first time.
for (const [where, file] of [
  ["onboarding", "app/onboarding.tsx"],
  ["settings", "app/preferences.tsx"],
]) {
  const src = readFileSync(file, "utf8");
  check(`${where} uses the picker`, /<AccentPicker/.test(src), true);
}
check("onboarding asks it as its own step",
  /step === "colour"/.test(readFileSync("app/onboarding.tsx", "utf8")), true);

// The context has to hand the choice out, or the app keeps the old colour
// while the storage holds the new one.
const ctx = readFileSync("src/contexts/AppContext.tsx", "utf8");
check("the context carries the accent", /accent: string;/.test(ctx), true);
check("and rebuilds when it changes",
  /theme, setTheme, accent, setAccent, userProfile,/.test(ctx), true);
check("an unknown stored id falls back",
  /accentById\(storedAccent\)\.id/.test(ctx), true);

// Every accent needs a name in every language the app speaks.
const strings = readFileSync("src/i18n/strings.ts", "utf8");
for (const accent of ACCENTS) {
  check(`${accent.labelKey} is defined`,
    new RegExp(`${accent.labelKey}:\\s*\\{`).test(strings), true);
  check(`${accent.labelKey} has Luxembourgish`,
    new RegExp(`${accent.labelKey}:\\s+"`).test(strings), true);
}

console.log(failures === 0
  ? `  test-contrast: all checks passed (${ACCENTS.length} accents, both modes)`
  : `  test-contrast: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
