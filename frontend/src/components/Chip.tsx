// A filter pill — "Iwwerall", "All Kantonen", a canton name.
//
// It used to import `palette` from the theme directly. That export is a
// constant: LIGHT_PALETTE, built once from the default accent. So every chip
// in the app was drawn in light-mode meadow green no matter what the reader
// had chosen — the active pill stayed the same green in dark mode, where the
// rest of the screen had moved on, and ignored a reader who picked blue.
//
// It also wrote white on that green. White on the light-mode `primary` is
// 4.5 : 1 and fine; on the dark-mode shade, which is deliberately bright so it
// reads against a dark ground, it is about 1.9 : 1 — a label you cannot read.

import React, { useMemo } from "react";
import { StyleSheet, Text, TouchableOpacity } from "react-native";

import { type EffectiveTheme, useAppPalette } from "@/src/hooks/useAppPalette";
import { activeFill, type Palette } from "@/src/theme";

type Props = {
  active?: boolean;
  onPress?: () => void;
  label: string;
  testID?: string;
};

export function Chip({ active, onPress, label, testID }: Props) {
  const { palette, effective } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, effective), [palette, effective]);
  return (
    <TouchableOpacity
      activeOpacity={0.85}
      onPress={onPress}
      style={[styles.chip, active ? styles.chipActive : styles.chipIdle]}
      testID={testID}
    >
      <Text
        style={[styles.label, active ? styles.labelActive : styles.labelIdle]}
        numberOfLines={1}
      >
        {label}
      </Text>
    </TouchableOpacity>
  );
}

const makeStyles = (palette: Palette, effective: EffectiveTheme) =>
  StyleSheet.create({
    chip: {
      flexShrink: 0,
      height: 36,
      paddingHorizontal: 16,
      borderRadius: 18,
      borderWidth: 1,
      justifyContent: "center",
      alignItems: "center",
    },
    chipIdle: {
      backgroundColor: palette.surface,
      borderColor: palette.border,
    },
    // See activeFill in theme.ts: in dark mode a pill filled with the bright
    // accent is a glowing sweet on a quiet screen, and white on it is 1.9 : 1.
    chipActive: {
      backgroundColor: activeFill(palette, effective).backgroundColor,
      borderColor: activeFill(palette, effective).borderColor,
    },
    label: { fontSize: 13, fontWeight: "600" },
    labelIdle: { color: palette.textSecondary },
    labelActive: { color: activeFill(palette, effective).color },
  });
