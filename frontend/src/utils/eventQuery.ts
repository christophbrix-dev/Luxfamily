// Turning the filter sheet into a question the server can answer.
//
// Every one of these used to be applied in the app, to whatever had been
// downloaded — which was 200 events out of 401. Choosing "Spillplaz" searched
// 200 rows and returned whatever happened to be among them; whether the one
// playground event was there depended on its date.
//
// The backend takes all of it now. Filtering where the data is means the
// answer covers everything, and the reply is small enough to be complete.

/** Everything the list screens can ask for. Empty fields are left out. */
export type EventQuery = {
  canton?: string | null;
  /** Any of these — the server treats several as an OR. */
  category?: readonly string[];
  /** "Indoor" | "Outdoor". "All" means do not ask. */
  type?: string | null;
  ageMin?: number | null;
  ageMax?: number | null;
  /** Only ever narrowing: false means "do not care", never "only the ones without". */
  wheelchair?: boolean;
  sensory?: boolean;
  freeParking?: boolean;
  /** ISO dates, inclusive. */
  dateFrom?: string | null;
  dateTo?: string | null;
  q?: string | null;
};

function iso(d: Date): string {
  // Local calendar date, not UTC. `toISOString` would roll over to tomorrow
  // for anyone east of Greenwich after their evening — which is Luxembourg,
  // every evening.
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/**
 * The window one of the DATE_OPTIONS chips means, relative to `today`.
 *
 * "Anytime" returns nothing to constrain, which is what an unset filter should
 * do. The weekend is the coming Saturday and Sunday; asked *on* a Saturday or
 * Sunday it means this one, because somebody looking for weekend plans on
 * Saturday morning means today.
 */
export function dateWindow(
  option: string,
  today: Date = new Date(),
): { dateFrom?: string; dateTo?: string } {
  const start = new Date(today);
  start.setHours(0, 0, 0, 0);

  if (option === "Today") {
    return { dateFrom: iso(start), dateTo: iso(start) };
  }

  if (option === "This weekend") {
    const day = start.getDay();              // 0 Sunday … 6 Saturday
    const saturday = new Date(start);
    if (day === 0) {
      saturday.setDate(start.getDate() - 1); // Sunday: the weekend is now
    } else {
      saturday.setDate(start.getDate() + ((6 - day + 7) % 7));
    }
    const sunday = new Date(saturday);
    sunday.setDate(saturday.getDate() + 1);
    // Never offer a Saturday that has already passed.
    const from = saturday < start ? start : saturday;
    return { dateFrom: iso(from), dateTo: iso(sunday) };
  }

  if (option === "Next 7 days") {
    const end = new Date(start);
    end.setDate(start.getDate() + 7);
    return { dateFrom: iso(start), dateTo: iso(end) };
  }

  return {};
}

/** "4-6" -> [4, 6]. "All" and anything unparseable -> nothing. */
export function ageWindow(option: string): { ageMin?: number; ageMax?: number } {
  const match = /^(\d{1,2})-(\d{1,2})$/.exec(option.trim());
  if (!match) return {};
  return { ageMin: Number(match[1]), ageMax: Number(match[2]) };
}

/**
 * The query string, leading "?" included, or "" when nothing is being asked.
 *
 * Booleans are sent only when true. Sending `wheelchair=false` would be
 * harmless today — the server reads it as "do not care" — but writing it out
 * invites the opposite reading later, and the switches are off by default.
 */
export function buildEventQuery(query: EventQuery = {}): string {
  const params = new URLSearchParams();

  if (query.canton) params.append("canton", query.canton);
  if (query.type && query.type !== "All") params.append("type", query.type);
  for (const category of query.category ?? []) params.append("category", category);

  if (typeof query.ageMin === "number") params.append("age_min", String(query.ageMin));
  if (typeof query.ageMax === "number") params.append("age_max", String(query.ageMax));

  if (query.wheelchair) params.append("wheelchair", "true");
  if (query.sensory) params.append("sensory", "true");
  if (query.freeParking) params.append("free_parking", "true");

  if (query.dateFrom) params.append("date_from", query.dateFrom);
  if (query.dateTo) params.append("date_to", query.dateTo);

  const trimmed = query.q?.trim();
  if (trimmed) params.append("q", trimmed);

  const rendered = params.toString();
  return rendered ? `?${rendered}` : "";
}
