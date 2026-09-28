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

/** One OpenStreetMap place as the map needs it. */
export type MapPlace = {
  id: string;
  lat: number;
  lng: number;
  name: string;
  group?: string;
  kindLabel?: string;
  btnLabel?: string;
};

/** Where the map is looking, so the screen can ask for the right places. */
export type MapView = {
  lat: number;
  lng: number;
  zoom: number;
  /** Half the diagonal of the visible area. */
  radiusKm: number;
};

export type LeafletMapHandle = {
  setEvents: (events: MapEvent[]) => void;
  setPlaces: (places: MapPlace[]) => void;
  focus: (lat: number, lng: number, zoom?: number) => void;
  flyToCanton: (canton: string) => void;
  flyToCountry: () => void;
  setTheme: (theme: "light" | "dark") => void;
};

type Props = {
  onMarkerTap?: (id: string) => void;
  /**
   * Several events on one coordinate were tapped.
   *
   * The map no longer fans them into a ring — see the note in leafletHtml.ts.
   * It hands the ids over instead, and the screen shows them as a list, which
   * is what a shared coordinate actually means.
   */
  onClusterTap?: (ids: string[]) => void;
  /** A place pin's button was pressed. */
  onPlaceTap?: (id: string, lat: number, lng: number) => void;
  /** The map settled somewhere new — sent on moveend/zoomend, debounced. */
  onViewChanged?: (view: MapView) => void;
  onReady?: () => void;
  style?: StyleProp<ViewStyle>;
};

const LeafletMap = forwardRef<LeafletMapHandle, Props>(function LeafletMap(
  { onMarkerTap, onClusterTap, onPlaceTap, onViewChanged, onReady, style },
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
    setPlaces: (places) => send({ type: "setPlaces", places }),
    setTheme: (theme) => send({ type: "setTheme", theme }),
  }));

  // The callbacks, always the current ones.
  //
  // The web listener below is attached once, on mount, and a listener attached
  // once keeps the closure it was created with. `onClusterTap` is rebuilt
  // whenever the event list changes, so the listener held the very first one —
  // the one that closed over an empty list. The map posted its message, the
  // bridge received it, the handler ran against nothing and opened nothing.
  // Exactly the kind of wiring that looks right in every file and does nothing
  // as a whole.
  const handlers = useRef({ onMarkerTap, onClusterTap, onPlaceTap, onViewChanged, onReady });
  handlers.current = { onMarkerTap, onClusterTap, onPlaceTap, onViewChanged, onReady };

  const handleMessage = (raw: string) => {
    try {
      const data = JSON.parse(raw);
      if (data.type === "ready") {
        readyRef.current = true;
        handlers.current.onReady?.();
        flush();
      } else if (data.type === "markerTap" && data.id) {
        handlers.current.onMarkerTap?.(data.id);
      } else if (data.type === "clusterTap" && Array.isArray(data.ids)) {
        const ids = data.ids.filter((id: unknown): id is string => typeof id === "string");
        if (ids.length > 0) handlers.current.onClusterTap?.(ids);
      } else if (data.type === "placeTap" && data.id) {
        handlers.current.onPlaceTap?.(data.id, data.lat, data.lng);
      } else if (data.type === "viewChanged" && typeof data.zoom === "number") {
        handlers.current.onViewChanged?.({
          lat: data.lat, lng: data.lng, zoom: data.zoom, radiusKm: data.radiusKm,
        });
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
