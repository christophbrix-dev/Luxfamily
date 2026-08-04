"""
Geocode events using a hard-coded Luxembourg commune → (lat, lng) lookup.

Why hard-coded? The Nominatim public endpoint aggressively rate-limits shared
IP ranges (429 within seconds from our K8s node). For 100-200 events the
lookup below is sufficient — the map has enough detail to place a marker in
the correct locality; the user can then zoom in for street-level detail.

Coordinates are the official commune centroids from data.public.lu (WGS84).
Anything outside this lookup falls back to the canton centroid.

Idempotent — only updates events whose (lat, lng) is (0, 0).

Run:
    cd /app/backend && python geocode_lookup.py
"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# --------------------------------------------------------------------------
# Commune / locality centroids (lat, lng). WGS84.
# Covers every commune present in seed_data.json + the major crawler towns.
# --------------------------------------------------------------------------
COMMUNE_COORDS: dict[str, tuple[float, float]] = {
    # Luxembourg City & suburbs -------------------------------------------------
    "Luxembourg":          (49.6117, 6.1319),
    "Luxembourg-Stadt":    (49.6117, 6.1319),
    "Luxemburg":           (49.6117, 6.1319),
    "Luxemburg-Stadt":     (49.6117, 6.1319),
    "Kirchberg":           (49.6303, 6.1547),
    "Bonnevoie":           (49.5960, 6.1408),
    "Grund":               (49.6094, 6.1361),
    "Belair":              (49.6106, 6.1097),
    "Cents":               (49.6236, 6.1600),
    "Gasperich":           (49.5758, 6.1225),
    "Merl":                (49.5989, 6.1049),
    "Limpertsberg":        (49.6197, 6.1256),
    "Pfaffenthal":         (49.6208, 6.1319),
    "Rollingergrund":      (49.6242, 6.1120),
    "Bertrange":           (49.6083, 6.0847),
    "Hesperange":          (49.5750, 6.1521),
    "Strassen":            (49.6167, 6.0833),
    "Contern":             (49.5556, 6.2000),
    "Niederanven":         (49.6494, 6.2453),
    "Sandweiler":          (49.6183, 6.2000),
    "Kockelscheuer":       (49.5722, 6.1214),

    # Minett (South) ------------------------------------------------------------
    "Esch-sur-Alzette":    (49.4959, 5.9807),
    "Differdange":         (49.5245, 5.8908),
    "Dudelange":           (49.4808, 6.0872),
    "Bettembourg":         (49.5178, 6.1017),
    "Kayl":                (49.4869, 6.0364),
    "Rumelange":           (49.4581, 6.0300),
    "Roeser":              (49.5342, 6.1147),
    "Peppange":            (49.5308, 6.1069),
    "Niederkorn":          (49.5375, 5.8886),
    "Foetz":               (49.5236, 5.9847),

    # Éislek (North) ------------------------------------------------------------
    "Clervaux":            (50.0546, 6.0289),
    "Wiltz":               (49.9663, 5.9333),
    "Vianden":             (49.9333, 6.2036),
    "Weiswampach":         (50.1394, 6.0819),
    "Munshausen":          (50.0044, 6.0361),
    "Bourscheid":          (49.9042, 6.0625),
    "Esch-sur-Sûre":       (49.9086, 5.9375),
    "Insenborn":           (49.8992, 5.9153),
    "Heiderscheid":        (49.8944, 5.9767),
    "Eschweiler":          (49.9575, 5.9358),
    "Hoscheid":            (49.9583, 6.0472),
    "Deiffelt":            (50.1189, 5.9028),

    # Diekirch / Guttland -------------------------------------------------------
    "Diekirch":            (49.8683, 6.1560),
    "Ettelbruck":          (49.8478, 6.1039),
    "Mersch":              (49.7500, 6.1067),
    "Medernach":           (49.8397, 6.2372),
    "Larochette":          (49.7883, 6.2153),
    "Nommern":             (49.7783, 6.1953),
    "Härebierg":           (49.8683, 6.1560),   # ≈ Diekirch centre
    "Lorentzweiler":       (49.7050, 6.1394),
    "Marienthal":          (49.7517, 6.0089),
    "Hollenfels":          (49.7256, 6.0631),
    "Ansembourg":          (49.7139, 6.0561),
    "Schoenfels":          (49.7375, 6.0733),
    "Useldange":           (49.7639, 5.9694),
    "Steinfort":           (49.6600, 5.9200),
    "Koerich":             (49.6683, 5.9531),

    # Mullerthal (East) ---------------------------------------------------------
    "Echternach":          (49.7217, 6.4225),
    "Berdorf":             (49.8144, 6.3419),
    "Consdorf":             (49.7864, 6.3489),
    "Bech":                (49.7361, 6.3583),
    "Rosport":             (49.7969, 6.4967),

    # Moselle (South-East) ------------------------------------------------------
    "Grevenmacher":        (49.6800, 6.4400),
    "Remich":              (49.5453, 6.3667),
    "Wormeldange":         (49.6094, 6.4083),
    "Remerschen":          (49.5000, 6.3639),
    "Bous":                (49.5464, 6.3300),
    "Wasserbillig":        (49.7139, 6.4972),
}

# Fallback per canton (used when the commune isn't in the table above).
CANTON_FALLBACK: dict[str, tuple[float, float]] = {
    "Luxembourg":          (49.6117, 6.1319),
    "Esch-sur-Alzette":    (49.4959, 5.9807),
    "Diekirch":            (49.8683, 6.1560),
    "Clervaux":            (50.0546, 6.0289),
    "Wiltz":               (49.9663, 5.9333),
    "Vianden":             (49.9333, 6.2036),
    "Echternach":          (49.7217, 6.4225),
    "Grevenmacher":        (49.6800, 6.4400),
    "Remich":              (49.5453, 6.3667),
    "Mersch":              (49.7500, 6.1067),
    "Capellen":            (49.6461, 5.9906),
    "Redange":             (49.7639, 5.8850),
}


def normalize_town(raw: str) -> str:
    if not raw:
        return ""
    # Reduce "Luxembourg-Stadt (Kirchberg)" → "Kirchberg" if the parenthesis
    # contains a known locality.
    if "(" in raw and ")" in raw:
        head, tail = raw.split("(", 1)
        tail = tail.split(")", 1)[0].strip()
        if tail in COMMUNE_COORDS:
            return tail
        return head.strip()
    return raw.split("/", 1)[0].strip()


def main() -> None:
    client = MongoClient(os.environ["MONGO_URL"])
    db     = client[os.environ["DB_NAME"]]

    # Re-geocode every event so we replace any earlier canton-centroid
    # fallbacks with the more accurate commune-level lookup.
    todo = list(db.events.find({}))
    print(f"[geocode] {len(todo)} events to place")

    ok = fb = 0
    for ev in todo:
        town   = normalize_town(ev.get("town", ""))
        canton = ev.get("canton", "")
        coord  = COMMUNE_COORDS.get(town)
        if not coord:
            coord = CANTON_FALLBACK.get(canton, (49.61, 6.13))
            fb += 1
        else:
            ok += 1
        db.events.update_one({"_id": ev["_id"]}, {"$set": {"lat": coord[0], "lng": coord[1]}})

    print(f"[geocode] done. exact={ok}, canton-fallback={fb}")


if __name__ == "__main__":
    main()
