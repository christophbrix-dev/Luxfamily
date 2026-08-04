import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import React, { useEffect, useState } from "react";
import { StyleSheet, Text } from "react-native";

import { useApp } from "@/src/contexts/AppContext";
import { fetchLuxembourgWeather, WeatherSnapshot, WEATHER_DESCRIPTIONS } from "@/src/utils/weather";

export function WeatherWidget({ testID }: { testID?: string }) {
  const { lang } = useApp();
  const [snap, setSnap] = useState<WeatherSnapshot | null>(null);

  useEffect(() => {
    let alive = true;
    fetchLuxembourgWeather().then((r) => {
      if (alive) setSnap(r);
    });
    return () => {
      alive = false;
    };
  }, []);

  const desc = snap ? WEATHER_DESCRIPTIONS[snap.weatherCode] ?? WEATHER_DESCRIPTIONS[3] : null;
  const label = desc ? desc[lang] : "...";
  const iconName = (desc?.icon ?? "partly-sunny-outline") as keyof typeof Ionicons.glyphMap;

  return (
    <LinearGradient
      colors={["#10B981", "#059669"]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.wrap}
      testID={testID ?? "weather-widget"}
    >
      <Ionicons name={iconName} size={20} color="#fff" />
      <Text style={styles.temp}>
        {snap ? `${snap.temperature}°C` : "--°C"}
      </Text>
      <Text style={styles.desc} numberOfLines={1}>
        · {label} · Luxembourg
      </Text>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 999,
    alignSelf: "flex-start",
    boxShadow: "0px 6px 12px rgba(16, 185, 129, 0.3)",
    elevation: 3,
  },
  temp: { color: "#fff", fontWeight: "800", fontSize: 14 },
  desc: { color: "rgba(255,255,255,0.9)", fontSize: 13, fontWeight: "500" },
});
