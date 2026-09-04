// Turning a failed request into something a person can act on.
//
// The password screen once showed "Unexpected non-whitespace character after
// JSON at position 4 (line 1 column 5)". The backend had answered "404 page not
// found" as plain text and the client parsed every body as JSON — "404" is a
// valid JSON number, so the parser got that far and then met a space.
//
// Anything that is not our own API answering can arrive as text or HTML: a
// gateway, a proxy, a maintenance page, a container that has not started. None
// of those should reach the reader as a parser complaint.
//
// Kept free of imports so it can be run directly by the test script — the rest
// of the API client pulls in React Native storage, which needs a bundler.

/** An HTTP failure, carrying the status so callers can tell 401 from 503. */
export class ApiError extends Error {
  // Written out rather than as a constructor parameter property: Node runs
  // these files by stripping types, and that shorthand is real syntax rather
  // than a type annotation, so it cannot be stripped.
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export type Body = { data: unknown; parsed: boolean };

/** Read a response body without assuming it is JSON. */
export function readBody(text: string): Body {
  if (!text) return { data: null, parsed: true };
  try {
    return { data: JSON.parse(text), parsed: true };
  } catch {
    return { data: null, parsed: false };
  }
}

/** The most useful sentence available for a failed request. */
export function describeHttpError(status: number, data: unknown, raw: string): string {
  const detail =
    data && typeof data === "object"
      ? (data as Record<string, unknown>).detail ?? (data as Record<string, unknown>).message
      : null;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail) return JSON.stringify(detail);

  // No JSON body. Say what the status means rather than quoting a stray
  // sentence out of somebody else's error page.
  if (status === 404) return "Not found on the server — is the backend up to date?";
  if (status === 401 || status === 403) return "Not allowed";
  if (status === 429) return "Too many attempts — wait a minute";
  if (status >= 500) return `Server error (${status})`;

  const trimmed = raw.trim();
  if (trimmed && trimmed.length < 120 && !trimmed.startsWith("<")) return trimmed;
  return `HTTP ${status}`;
}
