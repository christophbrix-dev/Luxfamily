import React from "react";
import { StyleSheet, Text, TouchableOpacity } from "react-native";

import { palette } from "@/src/theme";

type Props = {
  active?: boolean;
  onPress?: () => void;
  label: string;
  testID?: string;
};

export function Chip({ active, onPress, label, testID }: Props) {
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

const styles = StyleSheet.create({
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
  chipActive: {
    backgroundColor: palette.primary,
    borderColor: palette.primary,
  },
  label: { fontSize: 13, fontWeight: "600" },
  labelIdle: { color: palette.textSecondary },
  labelActive: { color: "#FFFFFF" },
});
