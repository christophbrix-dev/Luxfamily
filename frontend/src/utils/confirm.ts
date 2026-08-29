// Asking "are you sure?" in a way that works on every platform we run on.
//
// `Alert.alert` from react-native has no implementation on the web. Not a
// degraded one — react-native-web ships it as
//
//     class Alert { static alert() {} }
//
// an empty function. The dialog never appears, the button that opened it looks
// broken, and nothing is logged. The onboarding screen's "continue as guest"
// was exactly that: a control on the path every new user takes, dead in the
// browser and working on a phone, which is the hardest kind of bug to believe
// a report about.
//
// On web the browser's own confirm() is used. It is plain, but it is a real
// dialog that really blocks, and web is where this was broken.

import { Alert, Platform } from "react-native";

export type ConfirmOptions = {
  title: string;
  message: string;
  /** Label for the button that goes ahead. */
  confirmLabel: string;
  cancelLabel: string;
  /** Marks the action as destructive on iOS. Ignored elsewhere. */
  destructive?: boolean;
};

/**
 * Resolves true when the person confirmed, false when they cancelled or
 * dismissed. Never rejects — a dialog that cannot be shown counts as "no",
 * which is the safe answer for every caller we have.
 */
export function confirm(options: ConfirmOptions): Promise<boolean> {
  const { title, message, confirmLabel, cancelLabel, destructive } = options;

  if (Platform.OS === "web") {
    // globalThis rather than window: this module is imported by the node test
    // script, where window does not exist.
    const ask = (globalThis as { confirm?: (m?: string) => boolean }).confirm;
    if (typeof ask !== "function") return Promise.resolve(false);
    // The browser dialog has one text field, so title and body are joined.
    return Promise.resolve(ask(`${title}\n\n${message}`));
  }

  return new Promise((resolve) => {
    Alert.alert(title, message, [
      { text: cancelLabel, style: "cancel", onPress: () => resolve(false) },
      {
        text: confirmLabel,
        style: destructive ? "destructive" : "default",
        onPress: () => resolve(true),
      },
    ],
    // Tapping outside on Android dismisses without either handler firing;
    // without this the promise would never settle and the caller would wait
    // forever.
    { cancelable: true, onDismiss: () => resolve(false) });
  });
}
