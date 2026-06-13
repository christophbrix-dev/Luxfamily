import React from "react";
import { Platform, StyleSheet, View } from "react-native";
import { WebView } from "react-native-webview";

import { palette, radii } from "@/src/theme";

type Props = {
  lat: number;
  lng: number;
  label?: string;
  height?: number;
};

// OpenStreetMap embed via iframe — no API key needed. Works on iOS, Android & Web.
export function MapPreview({ lat, lng, label = "Place", height = 180 }: Props) {
  const bbox = `${lng - 0.005},${lat - 0.003},${lng + 0.005},${lat + 0.003}`;
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lng}`;
  const html = `
    <html><head><meta name="viewport" content="initial-scale=1, maximum-scale=1, user-scalable=no" /><style>
      html,body,iframe{margin:0;padding:0;border:0;width:100%;height:100%;}
    </style></head><body>
      <iframe src="${src}" allowfullscreen></iframe>
    </body></html>`;

  if (Platform.OS === "web") {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const IFrame: any = "iframe";
    return (
      <View style={[styles.wrap, { height }]} testID="map-preview">
        <IFrame
          title={label}
          src={src}
          style={{ border: 0, width: "100%", height: "100%" }}
          allowFullScreen
        />
      </View>
    );
  }

  return (
    <View style={[styles.wrap, { height }]} testID="map-preview">
      <WebView
        originWhitelist={["*"]}
        source={{ html }}
        style={styles.web}
        javaScriptEnabled
        domStorageEnabled
        scrollEnabled={false}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    width: "100%",
    borderRadius: radii.lg,
    overflow: "hidden",
    backgroundColor: palette.surfaceMuted,
  },
  web: { flex: 1, backgroundColor: "transparent" },
});
