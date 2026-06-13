import { Stack } from "expo-router";
import React from "react";
import { StyleSheet, View } from "react-native";

import { BottomTabBar } from "@/src/components/BottomTabBar";
import { palette } from "@/src/theme";

export default function TabsLayout() {
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

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: palette.background },
  content: { flex: 1 },
});
