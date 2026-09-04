/**
 * Language fallback helper for data records shaped `{en, de, fr, [lb]}`.
 *
 * Historical data files across the app declare their translations as
 * `{ en, de, fr }`. When the user picks Luxembourgish (`lb`) we would end
 * up reading `undefined`. This helper resolves any Lang code to a string,
 * falling back to German for `lb`, and to English otherwise.
 *
 * Usage:
 *   pickLang(persona.labels, lang)
 */
import type { Lang } from "@/src/data/places";

export type I18nField = Partial<Record<Lang, string>> & {
  en?: string;
  de?: string;
  fr?: string;
};

export function pickLang(field: I18nField | undefined, lang: Lang): string {
  if (!field) return "";
  if (lang === "lb") return field.lb ?? field.de ?? field.en ?? "";
  return field[lang] ?? field.en ?? field.de ?? "";
}


/**
 * The closest language a three-language lookup table can serve.
 *
 * For tables keyed by en/de/fr only — month names, chip labels — Luxembourgish
 * resolves to German, matching pickLang() and the fact that the two share most
 * of their vocabulary. Falling through to English would be the wrong neighbour.
 */
export function baseLang(lang: Lang): "en" | "de" | "fr" {
  return lang === "lb" ? "de" : lang;
}
