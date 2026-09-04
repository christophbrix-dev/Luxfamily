// One confirmation dialog for every platform we run on.
//
// The first attempt at this used `Alert.alert`, which react-native-web ships
// as `class Alert { static alert() {} }` — an empty function. The onboarding
// screen's skip button opened nothing in a browser and worked fine on a phone.
//
// The second attempt reached for the browser's own `confirm()` on web. That
// does appear, but it looks nothing like the rest of the app and it blocks the
// JavaScript thread, so the page freezes behind it — which is exactly what
// Emergent saw when it clicked the button three times and reported "the screen
// stays put".
//
// This is the third and last: `Modal` from react-native, the same component
// FilterSheet already uses and which demonstrably works in the web preview.
// One code path, our own styling, and a control an automated click can reach.

import { useMemo } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";

import { useAppPalette } from "@/src/hooks/useAppPalette";
import { radii, type Palette, shadowFor } from "@/src/theme";

type Props = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  /** Tints the confirm button as a warning. */
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel,
  destructive,
  onConfirm,
  onCancel,
}: Props) {
  const { palette, effective } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, effective), [palette, effective]);

  return (
    <Modal
      animationType="fade"
      transparent
      visible={open}
      // Android's back button and the web's Escape key both land here. Both
      // mean "no", never "yes".
      onRequestClose={onCancel}
      statusBarTranslucent
    >
      <Pressable style={styles.backdrop} onPress={onCancel} testID="confirm-backdrop" />
      <View style={styles.centre} pointerEvents="box-none">
        <View style={styles.card} testID="confirm-dialog">
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.message}>{message}</Text>
          <View style={styles.row}>
            <Pressable
              onPress={onCancel}
              style={({ pressed }) => [styles.btn, styles.cancel, pressed && styles.pressed]}
              testID="confirm-cancel"
            >
              <Text style={styles.cancelTxt}>{cancelLabel}</Text>
            </Pressable>
            <Pressable
              onPress={onConfirm}
              style={({ pressed }) => [
                styles.btn,
                destructive ? styles.destructive : styles.confirm,
                pressed && styles.pressed,
              ]}
              testID="confirm-ok"
            >
              <Text style={styles.confirmTxt}>{confirmLabel}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

function makeStyles(palette: Palette, effective: "light" | "dark") {
  return StyleSheet.create({
    backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(0,0,0,0.45)" },
    centre: {
      ...StyleSheet.absoluteFillObject,
      alignItems: "center",
      justifyContent: "center",
      padding: 24,
    },
    card: {
      width: "100%",
      maxWidth: 380,
      backgroundColor: palette.surface,
      borderRadius: radii.lg,
      padding: 22,
      gap: 10,
      ...shadowFor(effective),
    },
    title: { fontSize: 18, fontWeight: "700", color: palette.textPrimary },
    message: { fontSize: 15, lineHeight: 21, color: palette.textSecondary },
    row: { flexDirection: "row", gap: 10, marginTop: 12 },
    btn: { flex: 1, paddingVertical: 13, borderRadius: radii.md, alignItems: "center" },
    cancel: { backgroundColor: palette.surfaceMuted },
    confirm: { backgroundColor: palette.primary },
    destructive: { backgroundColor: palette.red },
    pressed: { opacity: 0.8 },
    cancelTxt: { fontSize: 15, fontWeight: "600", color: palette.textPrimary },
    confirmTxt: { fontSize: 15, fontWeight: "700", color: "#FFFFFF" },
  });
}
