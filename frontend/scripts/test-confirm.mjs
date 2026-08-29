// Tests for asking "are you sure?" on a platform where the usual way is a
// no-op.
//
// react-native-web ships Alert as
//
//     class Alert { static alert() {} }
//
// so the onboarding screen's "continue as guest" opened nothing in the browser
// and worked fine on a phone. Emergent found it while clicking through the
// preview and put it down to test timing; it was not timing.
//
//   node --experimental-strip-types scripts/test-confirm.mjs

let failures = 0;
function check(name, actual, expected) {
  if (actual !== expected) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

// A stand-in for react-native. The real module cannot be imported here: it
// needs a bundler and a running app. What is being tested is the branching and
// the promise, which is where the bug was.
const alertCalls = [];
const rn = {
  Platform: { OS: "web" },
  Alert: {
    alert(title, message, buttons, options) {
      alertCalls.push({ title, message, buttons, options });
    },
  },
};

// The module under test, with react-native swapped out. Kept as a literal copy
// of the branching in src/utils/confirm.ts — the point of this file is that
// the web branch exists at all and that both branches settle their promise.
function confirm({ title, message, confirmLabel, cancelLabel, destructive }) {
  if (rn.Platform.OS === "web") {
    const ask = globalThis.confirm;
    if (typeof ask !== "function") return Promise.resolve(false);
    return Promise.resolve(ask(`${title}\n\n${message}`));
  }
  return new Promise((resolve) => {
    rn.Alert.alert(title, message, [
      { text: cancelLabel, style: "cancel", onPress: () => resolve(false) },
      {
        text: confirmLabel,
        style: destructive ? "destructive" : "default",
        onPress: () => resolve(true),
      },
    ], { cancelable: true, onDismiss: () => resolve(false) });
  });
}

const opts = {
  title: "Ohne Angaben weiter?",
  message: "Dann können wir nichts vorschlagen.",
  confirmLabel: "Weiter",
  cancelLabel: "Abbrechen",
  destructive: true,
};

// --- web: the case that was broken ---------------------------------------
let asked = null;
globalThis.confirm = (m) => { asked = m; return true; };
check("web: a yes resolves true", await confirm(opts), true);
check("web: the dialog was actually opened", asked !== null, true);
check("web: it shows the warning text", asked.includes("nichts vorschlagen"), true);
check("web: it shows the title too", asked.includes("Ohne Angaben weiter?"), true);

globalThis.confirm = () => false;
check("web: a no resolves false", await confirm(opts), false);

// A browser without confirm, or one where it was suppressed. Must not hang.
delete globalThis.confirm;
check("web: no dialog available means no", await confirm(opts), false);

// --- native: still the platform dialog ------------------------------------
rn.Platform.OS = "ios";
alertCalls.length = 0;
const pending = confirm(opts);
check("native: goes through Alert.alert", alertCalls.length, 1);

const [{ buttons, options }] = alertCalls;
check("native: two buttons", buttons.length, 2);
check("native: cancel is marked as such", buttons[0].style, "cancel");
check("native: the destructive flag is passed on", buttons[1].style, "destructive");

buttons[1].onPress();
check("native: confirming resolves true", await pending, true);

alertCalls.length = 0;
const cancelled = confirm(opts);
alertCalls[0].buttons[0].onPress();
check("native: cancelling resolves false", await cancelled, false);

// Android dismisses by tapping outside, and neither handler fires. Without
// onDismiss the promise never settles and the caller waits forever.
alertCalls.length = 0;
const dismissed = confirm(opts);
check("native: dismissal is handled at all", typeof options.onDismiss, "function");
alertCalls[0].options.onDismiss();
check("native: dismissing resolves false", await dismissed, false);

// --- the shape the real module has to keep --------------------------------
const source = await import("node:fs").then((fs) =>
  fs.readFileSync(new URL("../src/utils/confirm.ts", import.meta.url), "utf8"));
check("the real module branches on Platform.OS", /Platform\.OS === "web"/.test(source), true);
check("the real module still handles onDismiss", /onDismiss/.test(source), true);

const onboarding = await import("node:fs").then((fs) =>
  fs.readFileSync(new URL("../app/onboarding.tsx", import.meta.url), "utf8"));
// Comments stripped first: the note explaining why the call is gone mentions
// it by name, and a test that its own subject matter can fail is no test.
const code = onboarding.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
check("onboarding no longer calls Alert.alert", /Alert\.alert/.test(code), false);
check("onboarding uses the helper", /from "@\/src\/utils\/confirm"/.test(onboarding), true);

console.log(failures === 0
  ? "  test-confirm: all checks passed"
  : `  test-confirm: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
