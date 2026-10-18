import { Stack } from "expo-router";
import React, { useMemo } from "react";
import { StyleSheet, View } from "react-native";

import { BottomTabBar } from "@/src/components/BottomTabBar";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { type Palette } from "@/src/theme";

export default function TabsLayout() {
  // The ground every tab is drawn on. With the frozen light palette this
  // was white behind every dark screen — visible as a flash on navigation
  // and wherever a screen did not cover the full height.
  const { palette } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette), [palette]);
  return (
    <View style={styles.wrap}>
      <View style={styles.content}>
        <Stack
          screenOptions={{
            headerShown: false,
            animation: "fade",
            contentStyle: { backgroundColor: palette.background },
          }}
        />
      </View>
      <BottomTabBar />
    </View>
  );
}

const makeStyles = (palette: Palette) =>
  StyleSheet.create({
    wrap: { flex: 1, backgroundColor: palette.background },
    content: { flex: 1 },
  });
