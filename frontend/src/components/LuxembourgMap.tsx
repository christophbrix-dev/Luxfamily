import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Defs, LinearGradient, Path, Stop } from "react-native-svg";

import type { Canton } from "@/src/data/places";
import { palette } from "@/src/theme";

const VIEW_W = 240;
const VIEW_H = 340;

// Simplified silhouette of Luxembourg, going clockwise from north.
const LUX_OUTLINE =
  "M88 18 L108 12 L142 36 L170 68 L188 86 L208 130 L228 178 L228 232 L224 280 L210 320 L184 332 L162 326 L132 330 L96 332 L62 318 L40 290 L24 248 L20 196 L34 152 L46 124 L52 96 L68 64 L78 36 Z";

type CantonNode = { key: Canton; x: number; y: number; short?: string };

const NODES: CantonNode[] = [
  { key: "Clervaux", x: 90, y: 56 },
  { key: "Wiltz", x: 60, y: 102 },
  { key: "Vianden", x: 145, y: 108 },
  { key: "Diekirch", x: 129, y: 144 },
  { key: "Redange", x: 50, y: 178 },
  { key: "Echternach", x: 188, y: 186, short: "Echt." },
  { key: "Mersch", x: 109, y: 196 },
  { key: "Grevenmacher", x: 190, y: 232, short: "Grev." },
  { key: "Capellen", x: 50, y: 240 },
  { key: "Luxembourg", x: 118, y: 258, short: "Lux." },
  { key: "Remich", x: 175, y: 282 },
  { key: "Esch-sur-Alzette", x: 78, y: 304, short: "Esch" },
];

type Props = {
  selected: Canton | null;
  counts: Record<string, number>;
  onSelect: (canton: Canton | null) => void;
};

export function LuxembourgMap({ selected, counts, onSelect }: Props) {
  return (
    <View style={styles.wrap}>
      <Svg
        width="100%"
        height={VIEW_H}
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        preserveAspectRatio="xMidYMid meet"
      >
        <Defs>
          <LinearGradient id="lux-bg" x1="0" y1="0" x2="1" y2="1">
            <Stop offset="0" stopColor="#ECFDF5" />
            <Stop offset="1" stopColor="#D1FAE5" />
          </LinearGradient>
        </Defs>

        <Path
          d={LUX_OUTLINE}
          fill="url(#lux-bg)"
          stroke={palette.primary}
          strokeWidth={1.4}
          strokeLinejoin="round"
        />
      </Svg>

      {/* Country label inside the silhouette */}
      <View style={[styles.countryLabel, { pointerEvents: "none" }]}>
        <Text style={styles.countryLabelTxt}>LUXEMBOURG</Text>
      </View>

      {/* Overlay clickable canton pills positioned in geographic space */}
      <View style={[StyleSheet.absoluteFill, { pointerEvents: "box-none" }]}>
        {NODES.map((n) => {
          const active = selected === n.key;
          const count = counts[n.key] ?? 0;
          const xPct = (n.x / VIEW_W) * 100;
          const yPct = (n.y / VIEW_H) * 100;
          const display = n.short ?? n.key;

          return (
            <Pressable
              key={n.key}
              onPress={() => onSelect(active ? null : n.key)}
              style={[
                styles.node,
                {
                  left: `${xPct}%`,
                  top: `${yPct}%`,
                },
                count === 0 && !active && styles.nodeEmpty,
              ]}
              hitSlop={6}
              testID={`canton-${n.key}`}
            >
              <View style={[styles.pill, active && styles.pillActive]}>
                <View style={[styles.dot, active && styles.dotActive]} />
                <Text
                  style={[styles.pillTxt, active && styles.pillTxtActive]}
                  numberOfLines={1}
                >
                  {display}
                </Text>
                {count > 0 ? (
                  <View style={[styles.badge, active && styles.badgeActive]}>
                    <Text style={[styles.badgeTxt, active && styles.badgeTxtActive]}>
                      {count}
                    </Text>
                  </View>
                ) : null}
              </View>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    width: "100%",
    height: VIEW_H,
    overflow: "hidden",
  },
  countryLabel: {
    position: "absolute",
    top: 4,
    alignSelf: "center",
    left: 0,
    right: 0,
    alignItems: "center",
  },
  countryLabelTxt: {
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 3,
    color: palette.primaryDark,
    opacity: 0.4,
  },
  node: {
    position: "absolute",
    transform: [{ translateX: -8 }, { translateY: -12 }],
  },
  nodeEmpty: { opacity: 0.55 },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingVertical: 4,
    paddingHorizontal: 6,
    paddingLeft: 5,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.95)",
    borderWidth: 1,
    borderColor: "rgba(16,185,129,0.18)",
    boxShadow: "0px 2px 4px rgba(15, 23, 42, 0.08)",
    elevation: 2,
  },
  pillActive: {
    backgroundColor: palette.primary,
    borderColor: palette.primary,
    boxShadow: "0px 4px 8px rgba(16, 185, 129, 0.45)",
    elevation: 4,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: palette.primary,
  },
  dotActive: {
    backgroundColor: "#fff",
  },
  pillTxt: {
    fontSize: 10,
    fontWeight: "700",
    color: palette.textPrimary,
    letterSpacing: -0.1,
  },
  pillTxtActive: { color: "#fff" },
  badge: {
    minWidth: 16,
    height: 14,
    paddingHorizontal: 4,
    borderRadius: 7,
    backgroundColor: palette.primaryDark,
    justifyContent: "center",
    alignItems: "center",
  },
  badgeActive: { backgroundColor: "#fff" },
  badgeTxt: { color: "#fff", fontSize: 9, fontWeight: "800" },
  badgeTxtActive: { color: palette.primary },
});
