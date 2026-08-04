// AUTO-GENERATED from /app/frontend/assets/leaflet_map.html
// If you edit leaflet_map.html, run: python3 -c "…" to regenerate.
export const LEAFLET_HTML = `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <title>Wat Elo? Map</title>

  <!-- Leaflet + MarkerCluster (public CDN, no API key) -->
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"
  />
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"
  />

  <style>
    html, body, #map {
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      background: #F0FDF4;
      font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif;
    }
    /* Custom emerald pin */
    .wat-pin {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      background: linear-gradient(135deg, #10B981 0%, #059669 100%);
      border: 3px solid #FFFFFF;
      box-shadow: 0 4px 10px rgba(15, 23, 42, 0.25);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: 700;
      font-size: 16px;
    }
    /* Featured / sponsored variant */
    .wat-pin.featured {
      background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);
    }
    /* Cluster styling */
    .marker-cluster-small,
    .marker-cluster-medium,
    .marker-cluster-large {
      background-color: rgba(16, 185, 129, 0.30);
    }
    .marker-cluster-small div,
    .marker-cluster-medium div,
    .marker-cluster-large div {
      background-color: #10B981;
      color: #ffffff;
      font-weight: 700;
    }
    .leaflet-popup-content-wrapper {
      border-radius: 14px;
      padding: 2px;
    }
    .leaflet-popup-content {
      margin: 12px 14px;
      font-size: 13px;
      line-height: 1.35;
    }
    .popup-title {
      font-weight: 700;
      color: #0F172A;
      font-size: 14px;
      margin-bottom: 4px;
    }
    .popup-meta {
      color: #64748B;
      font-size: 11px;
      margin-bottom: 8px;
    }
    .popup-btn {
      display: inline-block;
      padding: 6px 12px;
      background: #10B981;
      color: white;
      border-radius: 8px;
      text-decoration: none;
      font-weight: 600;
      font-size: 12px;
      cursor: pointer;
    }
    /* Hide the default marker shadow that ghosts through our custom pin */
    .leaflet-marker-shadow { display: none; }
  </style>
</head>
<body>
  <div id="map"></div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
          integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
          crossorigin=""></script>
  <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>

  <script>
    // ------------------------------------------------------------------
    // Map init — Luxembourg-centred, sensible default zoom, respectful
    // OpenStreetMap tile usage (attribution + subdomains).
    // ------------------------------------------------------------------
    const map = L.map("map", {
      zoomControl: true,
      attributionControl: true,
      preferCanvas: true,
    }).setView([49.7867, 6.0938], 9);

    // "Positron" CartoDB tiles read nicer for family-facing UI than the
    // stock OSM Mapnik style — but we fall back to OSM if unavailable.
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
      {
        attribution:
          '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: "abcd",
        maxZoom: 19,
      },
    ).addTo(map);

    const cluster = L.markerClusterGroup({
      showCoverageOnHover: false,
      maxClusterRadius: 45,
      spiderfyOnMaxZoom: true,
    });
    map.addLayer(cluster);

    // ------------------------------------------------------------------
    // Bridge between React Native / iframe host and the map.
    // Host sends messages of the form:
    //   { type: "setEvents", events: [{id,lat,lng,title,category,featured,town}, ...] }
    //   { type: "focus", lat, lng, zoom }
    //   { type: "flyToCanton", canton }
    // We send back:
    //   { type: "markerTap", id }
    // ------------------------------------------------------------------
    function postToHost(msg) {
      const data = JSON.stringify(msg);
      // React Native WebView
      if (window.ReactNativeWebView && window.ReactNativeWebView.postMessage) {
        window.ReactNativeWebView.postMessage(data);
      }
      // iframe on web
      if (window.parent && window.parent !== window) {
        window.parent.postMessage(data, "*");
      }
    }

    let currentMarkers = [];

    function categoryIcon(cats) {
      if (!Array.isArray(cats) || cats.length === 0) return "📍";
      const c = cats[0];
      if (c === "Playgrounds") return "🛝";
      if (c === "Animals")     return "🐾";
      if (c === "Nature")      return "🌳";
      if (c === "Culture")     return "🏛";
      if (c === "Sports")      return "⚽";
      if (c === "Workshops")   return "🎨";
      if (c === "Food")        return "🍽";
      if (c === "Indoor")      return "🏠";
      return "📍";
    }

    function makeIcon(event) {
      const emoji = categoryIcon(event.category);
      const cls   = event.featured ? "wat-pin featured" : "wat-pin";
      return L.divIcon({
        html: '<div class="' + cls + '">' + emoji + "</div>",
        className: "",
        iconSize:    [34, 34],
        iconAnchor:  [17, 17],
        popupAnchor: [0, -18],
      });
    }

    function makePopup(event) {
      const town = event.town ? '<div class="popup-meta">' + escapeHtml(event.town) +
                                (event.canton ? " · " + escapeHtml(event.canton) : "") + "</div>"
                              : "";
      const btnLabel = event.btnLabel || "Details";
      return (
        '<div class="popup-title">' + escapeHtml(event.title || "") + "</div>" +
        town +
        '<span class="popup-btn" data-event-id="' + escapeHtml(event.id) + '">' +
          escapeHtml(btnLabel) +
        "</span>"
      );
    }

    function escapeHtml(str) {
      return String(str ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }

    function setEvents(events) {
      cluster.clearLayers();
      currentMarkers = [];
      const valid = events.filter(
        (e) => typeof e.lat === "number" && typeof e.lng === "number" &&
               e.lat !== 0 && e.lng !== 0,
      );
      valid.forEach((event) => {
        const m = L.marker([event.lat, event.lng], { icon: makeIcon(event) });
        m.bindPopup(makePopup(event), { autoPan: true });
        m.on("popupopen", (e) => {
          const btn = e.popup._contentNode.querySelector(".popup-btn");
          if (btn) {
            btn.addEventListener("click", () => {
              postToHost({ type: "markerTap", id: event.id });
            });
          }
        });
        cluster.addLayer(m);
        currentMarkers.push({ m, event });
      });
      if (valid.length > 0) {
        const bounds = L.latLngBounds(valid.map((e) => [e.lat, e.lng]));
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
      }
    }

    // ------------------------------------------------------------------
    // Canton centroids for the "flyToCanton" command.
    // ------------------------------------------------------------------
    const CANTON_COORDS = {
      Luxembourg:         [49.6117, 6.1319],
      "Esch-sur-Alzette": [49.4959, 5.9807],
      Diekirch:           [49.8683, 6.1560],
      Clervaux:           [50.0546, 6.0289],
      Wiltz:              [49.9663, 5.9333],
      Vianden:            [49.9333, 6.2036],
      Echternach:         [49.7217, 6.4225],
      Grevenmacher:       [49.6800, 6.4400],
      Remich:             [49.5453, 6.3667],
      Mersch:             [49.7500, 6.1067],
      Capellen:           [49.6461, 5.9906],
      Redange:            [49.7639, 5.8850],
    };

    function handleMessage(msg) {
      try {
        const data = typeof msg === "string" ? JSON.parse(msg) : msg;
        if (data.type === "setEvents") {
          setEvents(data.events || []);
        } else if (data.type === "focus") {
          map.flyTo([data.lat, data.lng], data.zoom ?? 15, { duration: 0.8 });
        } else if (data.type === "flyToCanton") {
          const c = CANTON_COORDS[data.canton];
          if (c) map.flyTo(c, 12, { duration: 0.8 });
        } else if (data.type === "flyToCountry") {
          map.flyTo([49.7867, 6.0938], 9, { duration: 0.6 });
        }
      } catch (e) {
        // ignore malformed
      }
    }

    // React Native WebView delivers via document/window 'message' events.
    document.addEventListener("message", (ev) => handleMessage(ev.data));
    window.addEventListener("message", (ev) => handleMessage(ev.data));

    // Tell the host we're ready.
    postToHost({ type: "ready" });
  </script>
</body>
</html>
`;
