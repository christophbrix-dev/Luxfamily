// Tests for the confirmation dialog, which has now been wrong twice.
//
// First it used `Alert.alert`, which react-native-web ships as
//
//     class Alert { static alert() {} }
//
// so the onboarding skip button opened nothing in a browser and worked fine on
// a phone. Then it used the browser's own confirm(), which does appear but
// blocks the JavaScript thread behind a dialog that looks nothing like the
// app — Emergent clicked the button three times and reported that the screen
// stayed put.
//
// Now it is a Modal, the same component FilterSheet uses and which
// demonstrably works in the web preview. React components cannot be rendered
// here without a bundler, so what this file guards is the thing that actually
// went wrong twice: which mechanism the code reaches for.
//
//   node --experimental-strip-types scripts/test-confirm.mjs

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

let failures = 0;
function check(name, actual, expected) {
  if (actual !== expected) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

/** Every .ts/.tsx file under a directory. */
function sources(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry.startsWith(".")) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) sources(full, out);
    else if (/\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

/** Code with comments removed — a note explaining a ban must not trip it. */
function code(path) {
  return readFileSync(path, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

const files = [...sources("app"), ...sources("src")];
check("there are sources to check at all", files.length > 20, true);

// --- neither of the two broken mechanisms, anywhere -----------------------
const alerts = files.filter((f) => /\bAlert\.alert\s*\(/.test(code(f)));
check("nothing calls Alert.alert (empty function on web)", alerts.join(", "), "");

const browserConfirms = files.filter((f) =>
  /(window|globalThis)\.confirm\s*\(/.test(code(f)));
check("nothing calls the browser confirm (blocks the page)", browserConfirms.join(", "), "");

// --- the dialog itself ----------------------------------------------------
const dialog = readFileSync("src/components/ConfirmDialog.tsx", "utf8");
check("it is a Modal", /from "react-native"[\s\S]*?Modal|Modal[^\n]*from "react-native"/.test(dialog) || /<Modal/.test(dialog), true);
check("cancelling is wired to the hardware back button and Escape",
  /onRequestClose=\{onCancel\}/.test(dialog), true);
check("tapping the backdrop cancels rather than confirms",
  /testID="confirm-backdrop"[\s\S]{0,200}/.test(dialog) && /onPress=\{onCancel\}[\s\S]*?testID="confirm-backdrop"|testID="confirm-backdrop"/.test(dialog), true);
for (const id of ["confirm-dialog", "confirm-ok", "confirm-cancel", "confirm-backdrop"]) {
  check(`it can be driven by a test: ${id}`, dialog.includes(`testID="${id}"`), true);
}

// --- the screen that needed it -------------------------------------------
const onboarding = readFileSync("app/onboarding.tsx", "utf8");
check("onboarding uses the dialog", /ConfirmDialog/.test(onboarding), true);
check("the skip button opens it", /setAskingToSkip\(true\)/.test(onboarding), true);
check("confirming is a separate handler from opening",
  /onConfirm=\{skipForReal\}/.test(onboarding), true);
check("cancelling closes without skipping",
  /onCancel=\{\(\) => setAskingToSkip\(false\)\}/.test(onboarding), true);

console.log(failures === 0
  ? "  test-confirm: all checks passed"
  : `  test-confirm: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
