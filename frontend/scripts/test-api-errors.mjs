// Tests for turning a failed request into something a person can act on.
//
// The password screen showed "Unexpected non-whitespace character after JSON at
// position 4 (line 1 column 5)". The backend had answered "404 page not found"
// as plain text, and the client parsed every body as JSON: "404" is a valid
// JSON number, so the parser got that far and then met a space.
//
//   node --experimental-strip-types scripts/test-api-errors.mjs

import { ApiError, describeHttpError, readBody } from "../src/utils/apiError.ts";

let failures = 0;
function check(name, actual, expected) {
  if (actual !== expected) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}
function checkMatch(name, actual, re) {
  if (typeof actual !== "string" || !re.test(actual)) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        ${JSON.stringify(actual)} does not match ${re}`);
  }
}

/** What a real failure produces: read the body, then describe it. */
function describe(status, text) {
  const { data, parsed } = readBody(text);
  return describeHttpError(status, data, parsed ? "" : text);
}

// --- the failure that prompted this --------------------------------------
const real = describe(404, "404 page not found");
checkMatch("plain-text 404 is readable", real, /backend|not found/i);
check("nothing about JSON positions", /position \d/.test(real), false);
check('"404 page not found" is not read as the number 404',
  readBody("404 page not found").parsed, false);

// --- an HTML error page --------------------------------------------------
const html = describe(502, "<!DOCTYPE html><html><body>Bad Gateway</body></html>");
checkMatch("a gateway page becomes a server error", html, /server error/i);
check("no markup reaches the reader", /</.test(html), false);

// --- our own API, which does speak JSON ----------------------------------
check("the API's own wording wins",
  describe(403, JSON.stringify({ detail: "Current password is not correct" })),
  "Current password is not correct");
checkMatch("a structured detail is not lost",
  describe(400, JSON.stringify({ detail: [{ msg: "bad" }] })), /bad/);
check("a message field works too",
  describe(400, JSON.stringify({ message: "Nope" })), "Nope");

// --- statuses worth naming ----------------------------------------------
for (const [status, re] of [
  [401, /not allowed/i], [403, /not allowed/i],
  [429, /too many/i], [500, /server error/i], [503, /server error/i],
]) {
  checkMatch(`status ${status} with an empty body`, describe(status, ""), re);
}

// --- reading a body ------------------------------------------------------
check("an empty body counts as read", readBody("").parsed, true);
check("valid JSON is read", readBody('{"a":1}').parsed, true);
check("an array is read", Array.isArray(readBody("[]").data), true);
check("a bare number is still JSON", readBody("404").parsed, true);

// --- a short plain-text reason is worth quoting --------------------------
checkMatch("a terse server sentence survives", describe(400, "Missing field: email"), /Missing field/);

// --- the status travels with the error ----------------------------------
const err = new ApiError(429, "Too many attempts");
check("status is readable", err.status, 429);
check("it is an Error", err instanceof Error, true);

const total = 20;
if (failures) {
  console.log(`\n  ${failures} of ${total} checks failed`);
  process.exit(1);
}
console.log(`  api errors: ${total} checks passed`);
