// The accent colour, and the shades derived from it.
//
// Until now `primary` was a literal: #10B981, emerald-500. Measured against
// white text that is 2.54 : 1, and WCAG AA asks 4.5 : 1 for body text. Every
// green button in the app — "Resultater weisen", "Mat E-Mail weider" — sat
// below the line, and in dark mode white on #34D399 is 1.92 : 1. That is not a
// matter of taste; the label is genuinely hard to read.
//
// The shades are derived here rather than listed. Eight accents times six
// shades would be forty-eight hand-typed values nobody could check, and the
// first wrong one would look exactly like the other forty-seven. Derived, each
// is covered by scripts/test-contrast.mjs, which fails the build.
//
// Red and amber are missing on purpose. In this app `red` means "something
// went wrong" and `amber` means "careful". An accent sitting on either would
// give the confirm button and the error message the same colour.

/** An accent the reader can choose. `hue` is degrees on the colour wheel. */
export type Accent = {
  id: string;
  hue: number;
  /** i18n key for its name in the picker. */
  labelKey: string;
};

export const ACCENTS: readonly Accent[] = [
  { id: "meadow",  hue: 138, labelKey: "accentMeadow"  },
  { id: "grass",   hue: 145, labelKey: "accentGrass"   },
  { id: "emerald", hue: 160, labelKey: "accentEmerald" },
  { id: "teal",    hue: 185, labelKey: "accentTeal"    },
  { id: "blue",    hue: 214, labelKey: "accentBlue"    },
  { id: "violet",  hue: 265, labelKey: "accentViolet"  },
  { id: "pink",    hue: 330, labelKey: "accentPink"    },
  { id: "orange",  hue: 25,  labelKey: "accentOrange"  },
] as const;

/**
 * The default, chosen 2026-09-30: a green one step warmer than the old one.
 *
 * Blue stays out of the default seat for a reason unrelated to taste — on the
 * map blue already means "place": playgrounds, picnic spots and route lines
 * are drawn with it. It is still offered; choosing it only means the map needs
 * another colour for places.
 */
export const DEFAULT_ACCENT = "meadow";

export function accentById(id: string | null | undefined): Accent {
  const found = ACCENTS.find((a) => a.id === id);
  if (found) return found;
  // The default is in the list, so this never returns undefined — but saying
  // so with a `!` would hide the day somebody removes it.
  return ACCENTS.find((a) => a.id === DEFAULT_ACCENT) ?? ACCENTS[0];
}

// ---------------------------------------------------------------------------
// Colour arithmetic
// ---------------------------------------------------------------------------

/** HSL to hex. Lightness and saturation are percentages. */
export function hsl(hue: number, lightness: number, saturation: number): string {
  const h = ((((hue % 360) + 360) % 360)) / 360;
  const l = Math.min(1, Math.max(0, lightness / 100));
  const s = Math.min(1, Math.max(0, saturation / 100));

  if (s === 0) {
    const v = Math.round(l * 255);
    return toHex(v, v, v);
  }
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const component = (t: number) => {
    let x = t;
    if (x < 0) x += 1;
    if (x > 1) x -= 1;
    if (x < 1 / 6) return p + (q - p) * 6 * x;
    if (x < 1 / 2) return q;
    if (x < 2 / 3) return p + (q - p) * (2 / 3 - x) * 6;
    return p;
  };
  return toHex(
    Math.round(component(h + 1 / 3) * 255),
    Math.round(component(h) * 255),
    Math.round(component(h - 1 / 3) * 255),
  );
}

function toHex(r: number, g: number, b: number): string {
  return "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0").toUpperCase()).join("");
}

/** Relative luminance, WCAG 2.1. */
export function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const channel = (pair: string) => {
    const v = parseInt(pair, 16) / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(h.slice(0, 2))
       + 0.7152 * channel(h.slice(2, 4))
       + 0.0722 * channel(h.slice(4, 6));
}

/** Contrast ratio between two colours, from 1 : 1 to 21 : 1. */
export function contrast(a: string, b: string): number {
  const la = luminance(a), lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/**
 * The lightest shade of this hue that still carries text at `target`.
 *
 * Lightest, not safest: every step darker is a step towards mud, and the point
 * of an accent is that it is the colour of the app. The loop walks down from a
 * light value and stops at the first that qualifies.
 */
function lightestOver(hue: number, saturation: number, over: string, target: number): string {
  for (let l = 58; l >= 12; l -= 1) {
    const candidate = hsl(hue, l, saturation);
    if (contrast(candidate, over) >= target) return candidate;
  }
  return hsl(hue, 12, saturation);
}

/**
 * The accent shades a palette needs, for one mode.
 *
 * Five and not three: the app was already using five, four of them as literals
 * scattered through the screens. Naming them is what lets a chosen accent
 * reach the pale section grounds and the hairline borders, instead of leaving
 * an emerald tint behind on a blue app.
 */
export type AccentShades = {
  /** Button fills and active states. Carries white text in light mode. */
  primary: string;
  /** Accent text on a pale ground; in dark mode the emphatic, brighter shade. */
  primaryDark: string;
  /** Badge and chip backgrounds. */
  primaryLight: string;
  /** The palest tint: section grounds, gradients' far end. */
  primarySoft: string;
  /** Hairline borders around tinted areas. */
  primaryBorder: string;
};

/**
 * The colour the map draws places with — playgrounds, picnic spots, routes.
 *
 * Derived from the accent by rotating half a turn, so it is as far from it as
 * a hue can be whatever the reader chose. A fixed colour could not do that:
 * every hue is on the list, so any fixed choice collides with one of them.
 * Blue was the fixed choice until now, and choosing blue made events and
 * places the same colour on the map.
 *
 * Saturation is held below the accent's so the accent stays the louder of the
 * two: places are the backdrop a reader scans, events are what they came for.
 */
/**
 * The colour the map draws places with — playgrounds, picnic spots, routes.
 *
 * A slate, and deliberately not a hue related to the accent.
 *
 * Rotating away from the accent was the first idea and it does not survive
 * contact with the palette: for a blue app the opposite third lands among the
 * warm hues, where the map's amber (featured events) and the app's red
 * (errors) already live. Half a turn from blue is 34°, all but that amber.
 * There is no rotation that clears every accent and both semantic colours,
 * because the accents cover the wheel.
 *
 * A neutral clears all of them at once, and it is the better design anyway:
 * places are the backdrop a reader scans across, events are what they came
 * for. The accent should be the loudest thing on the map.
 */
export function placeColourFor(_hue: number, mode: "light" | "dark"): [string, string] {
  return mode === "light"
    ? ["#64748B", "#475569"]   // slate-500 / slate-600
    : ["#94A3B8", "#CBD5E1"];  // slate-400 / slate-300, against inverted tiles
}

/**
 * A gradient in the accent, from the fill towards its darker end.
 *
 * Two headers use one — the language picker and the weather strip — and both
 * had it written out as three emerald literals.
 */
export function gradientFor(hue: number, mode: "light" | "dark"): [string, string, string] {
  const s = shadesFor(hue, mode);
  return mode === "light"
    ? [s.primary, s.primaryDark, hsl(hue, 22, 74)]
    : [s.primaryLight, hsl(hue, 22, 50), hsl(hue, 14, 45)];
}

/** Surfaces the shades are measured against, from the palettes below. */
export const LIGHT_SURFACE = "#FFFFFF";
export const DARK_SURFACE = "#1F2937";

export function shadesFor(hue: number, mode: "light" | "dark"): AccentShades {
  if (mode === "light") {
    return {
      primary:      lightestOver(hue, 72, LIGHT_SURFACE, 4.5),
      // 7 : 1 here rather than 4.5: this is accent text on a white card, where
      // the lower threshold is a floor rather than a comfortable place to sit.
      primaryDark:  lightestOver(hue, 74, LIGHT_SURFACE, 7.0),
      primaryLight: hsl(hue, 93, 70),
      primarySoft:  hsl(hue, 97, 65),
      primaryBorder: hsl(hue, 84, 62),
    };
  }
  // The base: dimmest that still reads on the surface. Measured against the
  // surface rather than the background because the surface is the lighter of
  // the two, so passing there passes on both.
  const saturation = 70;
  let baseL = 52;
  while (baseL < 92 && contrast(hsl(hue, baseL, saturation), DARK_SURFACE) < 4.5) baseL += 1;
  const primary = hsl(hue, baseL, saturation);

  // The emphatic shade, walked upward *from the base*.
  //
  // In dark mode "darker" is the wrong idea — the ground is already dark, so
  // the emphatic shade is the brighter one. Two earlier attempts got this
  // wrong in different ways: deriving it from a 7 : 1 threshold gave meadow
  // the same value twice, and searching from a fixed lightness handed violet
  // a *darker* shade that happened to sit far enough from the base. Starting
  // at baseL + 1 is the only version that can only go up.
  let brightL = baseL + 1;
  while (brightL < 95 && contrast(hsl(hue, brightL, saturation), primary) < 1.35) brightL += 1;

  return {
    primary,
    primaryDark:  hsl(hue, brightL, saturation),
    primaryLight: hsl(hue, 15, 45),
    primarySoft:  hsl(hue, 11, 40),
    primaryBorder: hsl(hue, 24, 45),
  };
}
