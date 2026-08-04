/**
 * Cross-platform Leaflet map wrapper.
 *
 * - Web  (Metro/react-native-web): renders an <iframe srcDoc="…" /> so we can
 *   ship the map HTML without a backend endpoint.
 * - Native (iOS/Android): renders react-native-webview with `source={{ html: … }}`.
 *
 * Both sides talk to the map via postMessage using the schema in leaflet_map.html.
 */
import React, { forwardRef, useImperativeHandle, useRef, useEffect } from "react";
import { Platform, View, StyleSheet, StyleProp, ViewStyle } from "react-native";
import type WebViewType from "react-native-webview";
import { LEAFLET_HTML } from "./leafletHtml";

export type MapEvent = {
  id: string;
  lat: number;
  lng: number;
  title: string;
  town?: string;
  canton?: string;
  category?: string[];
  featured?: boolean;
  btnLabel?: string;
};

export type LeafletMapHandle = {
  setEvents: (events: MapEvent[]) => void;
  focus: (lat: number, lng: number, zoom?: number) => void;
  flyToCanton: (canton: string) => void;
  flyToCountry: () => void;
};

type Props = {
  onMarkerTap?: (id: string) => void;
  onReady?: () => void;
  style?: StyleProp<ViewStyle>;
};

const LeafletMap = forwardRef<LeafletMapHandle, Props>(function LeafletMap(
  { onMarkerTap, onReady, style },
  ref,
) {
  // Native WebView ref (only used on iOS / Android).
  const webRef = useRef<WebViewType | null>(null);
  // Web iframe ref
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  // Track "ready" so we buffer setEvents calls issued before load.
  const readyRef  = useRef(false);
  const bufferRef = useRef<object[]>([]);

  const send = (msg: object) => {
    const str = JSON.stringify(msg);
    if (!readyRef.current) {
      bufferRef.current.push(msg);
      return;
    }
    if (Platform.OS === "web") {
      iframeRef.current?.contentWindow?.postMessage(str, "*");
    } else {
      webRef.current?.injectJavaScript(
        `window.postMessage(${JSON.stringify(str)}, "*"); true;`,
      );
    }
  };

  const flush = () => {
    while (bufferRef.current.length) {
      const msg = bufferRef.current.shift();
      if (msg) send(msg);
    }
  };

  useImperativeHandle(ref, () => ({
    setEvents: (events) => send({ type: "setEvents", events }),
    focus: (lat, lng, zoom) => send({ type: "focus", lat, lng, zoom }),
    flyToCanton: (canton) => send({ type: "flyToCanton", canton }),
    flyToCountry: () => send({ type: "flyToCountry" }),
  }));

  const handleMessage = (raw: string) => {
    try {
      const data = JSON.parse(raw);
      if (data.type === "ready") {
        readyRef.current = true;
        onReady?.();
        flush();
      } else if (data.type === "markerTap" && data.id) {
        onMarkerTap?.(data.id);
      }
    } catch {
      // ignore malformed
    }
  };

  // Web: attach postMessage listener for iframe → parent bridge.
  useEffect(() => {
    if (Platform.OS !== "web") return;
    const onMsg = (ev: MessageEvent) => {
      if (typeof ev.data !== "string") return;
      handleMessage(ev.data);
    };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (Platform.OS === "web") {
    return (
      <View style={[styles.wrap, style]}>
        {/*
          React Native Web renders <View> as <div>; we drop an iframe inside.
          The `srcDoc` attribute is applied via a native DOM ref because
          RN Web strips unknown props.
        */}
        <iframe
          ref={iframeRef}
          srcDoc={LEAFLET_HTML}
          style={iframeStyle}
          title="Wat Elo? Map"
          sandbox="allow-scripts allow-same-origin allow-popups"
        />
      </View>
    );
  }

  // Native — lazy-require react-native-webview so we never load its DOM
  // shim on web (fails the bundler otherwise).
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { WebView } = require("react-native-webview") as typeof import("react-native-webview");

  return (
    <View style={[styles.wrap, style]}>
      <WebView
        ref={(r) => {
          webRef.current = r;
        }}
        originWhitelist={["*"]}
        source={{ html: LEAFLET_HTML }}
        onMessage={(ev) => handleMessage(ev.nativeEvent.data)}
        javaScriptEnabled
        domStorageEnabled
        allowFileAccess
        androidLayerType="hardware"
        style={styles.web}
      />
    </View>
  );
});

const styles = StyleSheet.create({
  wrap: { flex: 1, overflow: "hidden", backgroundColor: "#F0FDF4" },
  web:  { flex: 1, backgroundColor: "transparent" },
});

// react-native-web ignores custom iframe styling via `style` prop when
// wrapped inside <View>; use raw CSS.
const iframeStyle: React.CSSProperties = {
  width: "100%",
  height: "100%",
  border: "0",
  display: "block",
};

export default LeafletMap;
