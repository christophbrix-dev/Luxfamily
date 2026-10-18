// When an entry is relevant, and what the card should say about its dates.
//
// The list used to show an event from the day it started onwards, which for a
// concert is the same thing and for 135 multi-day entries is not. "Mount vum
// Bongert" runs the whole of October; it was in the app on 1 October and gone
// on the 2nd. Nine events were running on the day this was written and the app
// showed none of them.
//
// No imports on purpose. The rule is small, it decides what a reader sees, and
// a leaf module is the shape this codebase can test — scripts/test-event-dates
// runs it directly.

/** A date-only ISO string, YYYY-MM-DD. Comparable with `<` as plain text. */
export type IsoDate = string;

export type DatedEntry = {
  start_date: IsoDate;
  end_date?: IsoDate | null;
};

/**
 * The first day this entry is still relevant, seen from `today`.
 *
 * `max(start_date, today)`: something running since August is relevant now,
 * not in August. Sorting and grouping by the raw start date put it at the top
 * of the list under an "August" heading, in a list of things still to come.
 *
 * The backend sorts by the same rule. It is expressed twice because it is a
 * display decision on one side and an index decision on the other — the thing
 * to keep identical is the rule, and both sides have it in a named function
 * with tests rather than inline in a comparison.
 */
export function relevantFrom(startDate: IsoDate, today: IsoDate): IsoDate {
  return startDate < today ? today : startDate;
}

/**
 * What the card should say about the dates, beyond the day in the date box.
 *
 * Three cases, and the difference between the last two is the difference
 * between knowing and guessing:
 *
 *  - `none` — it starts today or later. The date box already says everything.
 *  - `runsUntil` — it began earlier and states an end that has not passed.
 *    We know it is on; the card can say so and name the last day.
 *  - `startedOn` — it began earlier and states no end. 299 of 1,435 events are
 *    in this shape. Whether it is still on is not in the data, so the card
 *    says when it started and claims nothing further.
 */
export type DateNote =
  | { kind: "none" }
  | { kind: "runsUntil"; date: IsoDate }
  | { kind: "startedOn"; date: IsoDate };

export function dateNote(entry: DatedEntry, today: IsoDate): DateNote {
  if (entry.start_date >= today) return { kind: "none" };
  if (entry.end_date && entry.end_date >= today) {
    return { kind: "runsUntil", date: entry.end_date };
  }
  return { kind: "startedOn", date: entry.start_date };
}

/**
 * The day to print in the card's date box.
 *
 * For a running event that is today, not the day it began: the box answers
 * "when can I go", and "31 AUG" on something you can visit this afternoon
 * reads as an error. The note beside it carries the real span.
 */
export function boxDate(entry: DatedEntry, today: IsoDate): IsoDate {
  return relevantFrom(entry.start_date, today);
}

/**
 * Today's date in the reader's own calendar, as YYYY-MM-DD.
 *
 * Not `toISOString().slice(0, 10)`, which is UTC: between midnight and 01:00
 * or 02:00 Luxembourg time that still returns yesterday, and every event of
 * the new day would be labelled as having started "yesterday" for the first
 * hours of its own morning.
 */
export function todayIso(now: Date = new Date()): IsoDate {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
