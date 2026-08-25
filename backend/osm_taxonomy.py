"""
OSM POI taxonomy for Wat Elo? — 7 groups / ~30 kinds tailored to
family-friendly spots in Luxembourg.

Each `CATEGORIES[key]` entry contains:
    label_de / label_fr / label_lb / label_en : human labels (Lëtzebuergesch first)
    filters   : list of Overpass QL filter chunks (["key"="value"]...)
    relations_only : if True, query only relations (used for routes)
    group     : parent bucket that maps into the UI's category filter
    base_score: seed value for the family_score, refined by SCORE_RULES

The Overpass builder in osm_ingest.py wraps every filter with `(area.lu);`
and collects the result via `out center tags;`.
"""

# -------- Groups (used as UI filter buckets) -------------------------
GROUPS = {
    "play":     {"label_de": "Spielen",             "label_fr": "Jouer",              "label_lb": "Spillen",              "label_en": "Play",              "color": "#EC4899"},
    "nature":   {"label_de": "Natur & Grün",        "label_fr": "Nature & Verdure",   "label_lb": "Natur & Gréngs",       "label_en": "Nature & Green",    "color": "#10B981"},
    "picnic":   {"label_de": "Picknick & Rast",     "label_fr": "Pique-nique & Repos","label_lb": "Picknick & Rascht",    "label_en": "Picnic & Rest",     "color": "#F59E0B"},
    "hike":     {"label_de": "Wandern & Wege",      "label_fr": "Randonnée & Chemins","label_lb": "Wanderen & Weeër",     "label_en": "Hiking & Trails",   "color": "#84CC16"},
    "animals":  {"label_de": "Tiere & Bauernhöfe",  "label_fr": "Animaux & Fermes",   "label_lb": "Déieren & Bauerenhaff","label_en": "Animals & Farms",   "color": "#F97316"},
    "culture":  {"label_de": "Kultur & Lernen",     "label_fr": "Culture & Apprentissage","label_lb": "Kultur & Léieren","label_en": "Culture & Learning","color": "#8B5CF6"},
    "sport":    {"label_de": "Sport & Schwimmen",   "label_fr": "Sport & Natation",   "label_lb": "Sport & Schwammen",    "label_en": "Sport & Swimming",  "color": "#0EA5E9"},
}


# -------- Categories (Kind) -----------------------------------------
# Filters are given as Overpass QL fragments (without brackets around the
# opening tag). The builder wraps each fragment with node/way/relation as
# appropriate and appends `(area.lu);`.
CATEGORIES = {
    # ---------- Spielen ----------
    "playground": {
        "label_de": "Spielplatz", "label_fr": "Aire de jeux",
        "label_lb": "Spillplaz",  "label_en": "Playground",
        "group": "play", "base_score": 90,
        "filters": ['["leisure"="playground"]'],
    },
    "water_playground": {
        "label_de": "Wasserspielplatz", "label_fr": "Aire de jeux d'eau",
        "label_lb": "Waasserspillplaz", "label_en": "Water playground",
        "group": "play", "base_score": 88,
        "filters": [
            '["leisure"="water_park"]',
            '["playground"="splash_pad"]',
            '["amenity"="fountain"]["drinking_water"="yes"]',
        ],
    },
    "skatepark": {
        "label_de": "Skatepark / Pumptrack", "label_fr": "Skatepark / Pumptrack",
        "label_lb": "Skatepark / Pumptrack", "label_en": "Skatepark / Pumptrack",
        "group": "play", "base_score": 75,
        "filters": [
            '["leisure"="skatepark"]',
            '["leisure"="pitch"]["sport"="skateboard"]',
            '["leisure"="pitch"]["sport"="cycling"]["cycling"="pumptrack"]',
        ],
    },
    "indoor_play": {
        "label_de": "Indoor-Spielplatz", "label_fr": "Aire de jeux couverte",
        "label_lb": "Indoor-Spillplaz",  "label_en": "Indoor play",
        "group": "play", "base_score": 85,
        "filters": [
            '["leisure"="indoor_play"]',
            '["leisure"="adventure_park"]',
            '["attraction"="soft_play"]',
        ],
    },
    "minigolf": {
        "label_de": "Minigolf", "label_fr": "Mini-golf",
        "label_lb": "Minigolf", "label_en": "Mini golf",
        "group": "play", "base_score": 70,
        "filters": ['["leisure"="miniature_golf"]'],
    },

    # ---------- Natur & Grün ----------
    "park": {
        "label_de": "Park / Garten", "label_fr": "Parc / Jardin",
        "label_lb": "Park / Gaart",  "label_en": "Park / Garden",
        "group": "nature", "base_score": 70,
        "filters": [
            '["leisure"="park"]',
            '["leisure"="garden"]["access"!~"^(private|no|customers)$"]',
        ],
    },
    "nature_reserve": {
        "label_de": "Naturschutzgebiet", "label_fr": "Réserve naturelle",
        "label_lb": "Naturschutzgebitt", "label_en": "Nature reserve",
        "group": "nature", "base_score": 60,
        "filters": [
            '["leisure"="nature_reserve"]',
            '["boundary"="protected_area"]',
        ],
    },
    "viewpoint": {
        "label_de": "Aussichtspunkt", "label_fr": "Point de vue",
        "label_lb": "Aussiichtspunkt", "label_en": "Viewpoint",
        "group": "nature", "base_score": 55,
        "filters": [
            '["tourism"="viewpoint"]',
            '["man_made"="tower"]["tower:type"]',
        ],
    },
    "water": {
        "label_de": "Baden / See / Strand", "label_fr": "Baignade / Lac / Plage",
        "label_lb": "Baden / Séi / Plage",  "label_en": "Bathing / Lake / Beach",
        "group": "nature", "base_score": 80,
        "filters": [
            '["leisure"="swimming_area"]',
            '["natural"="beach"]',
            '["sport"="swimming"]["natural"="water"]',
        ],
    },
    # Luxembourg's bathing lakes. They are tagged natural=water + water=lake
    # and nothing else — no swimming_area, no beach — so the category above
    # never matched a single one, and the Lac d'Echternach was missing from an
    # app about family outings in Luxembourg.
    #
    # Matching water=lake on its own is useless: 3,110 unnamed ponds sit inside
    # the country's bounding box. A name cuts that to 41, and a minimum size
    # settles the rest — a storm basin called "A2" is 0.4 ha, a lake people
    # drive to is not. At 2 ha the whole country yields exactly four: Haute-
    # Sûre, Echternach, the Riemescher Weieren and Weiswampach. Which is the
    # right answer, because that is how many bathing lakes Luxembourg has.
    #
    # water=reservoir stays out deliberately: at this size it means the upper
    # basins at Vianden, which are fenced industrial pumped storage.
    "lake": {
        "label_de": "Badesee", "label_fr": "Lac de baignade",
        "label_lb": "Badeséi", "label_en": "Bathing lake",
        "group": "nature", "base_score": 85,
        "filters": ['["natural"="water"]["water"="lake"]'],
        "require_name": True,
        "min_area_m2": 20_000,
    },
    "cave_rock": {
        "label_de": "Höhle / Fels", "label_fr": "Grotte / Rocher",
        "label_lb": "Buedem / Fiels", "label_en": "Cave / Rock",
        "group": "nature", "base_score": 65,
        "filters": [
            '["natural"="cave_entrance"]',
            '["natural"="rock"]["name"]',
        ],
    },

    # ---------- Picknick & Rast ----------
    "picnic": {
        "label_de": "Picknickplatz", "label_fr": "Aire de pique-nique",
        "label_lb": "Picknickplaz",  "label_en": "Picnic site",
        "group": "picnic", "base_score": 82,
        "filters": [
            '["tourism"="picnic_site"]',
            '["leisure"="picnic_table"]',
        ],
    },
    "bbq": {
        "label_de": "Grillplatz / Feuerstelle", "label_fr": "Barbecue / Foyer",
        "label_lb": "Grillplaz",                 "label_en": "BBQ / Firepit",
        "group": "picnic", "base_score": 78,
        "filters": [
            '["amenity"="bbq"]',
            '["leisure"="firepit"]',
        ],
    },
    "shelter": {
        "label_de": "Schutzhütte", "label_fr": "Abri",
        "label_lb": "Schutzhaischen", "label_en": "Shelter",
        "group": "picnic", "base_score": 60,
        "filters": [
            '["amenity"="shelter"]["shelter_type"~"picnic_shelter|weather_shelter"]',
            '["tourism"="wilderness_hut"]',
        ],
    },

    # ---------- Wandern & Wege ----------
    "hiking_route": {
        "label_de": "Wanderweg", "label_fr": "Sentier de randonnée",
        "label_lb": "Wanderwee", "label_en": "Hiking route",
        "group": "hike", "base_score": 70, "relations_only": True,
        "filters": [
            '["route"="hiking"]["type"=" route"]'.replace(" route", "route"),
            '["route"="foot"]["type"="route"]',
        ],
    },
    "nature_trail": {
        "label_de": "Themenpfad / Naturlehrpfad", "label_fr": "Sentier didactique",
        "label_lb": "Naturléierwee",              "label_en": "Nature trail",
        "group": "hike", "base_score": 68,
        "filters": [
            '["information"="route_marker"]["hiking"="yes"]["name"]',
            '["tourism"="information"]["information"="board"]["board_type"~"natur"]',
        ],
    },
    "cycle_route": {
        "label_de": "Radweg", "label_fr": "Piste cyclable",
        "label_lb": "Vëlospiste", "label_en": "Cycle route",
        "group": "hike", "base_score": 60, "relations_only": True,
        "filters": ['["route"="bicycle"]["type"="route"]'],
    },
    "fitness_trail": {
        "label_de": "Fitnessparcours", "label_fr": "Parcours fitness",
        "label_lb": "Fitnessparcours", "label_en": "Fitness trail",
        "group": "hike", "base_score": 55,
        "filters": [
            '["leisure"="fitness_station"]',
            '["route"="fitness_trail"]',
        ],
    },

    # ---------- Tiere & Bauernhöfe ----------
    "farm": {
        "label_de": "Bauernhof / Hofladen", "label_fr": "Ferme / Vente à la ferme",
        "label_lb": "Bauerenhaff",          "label_en": "Farm / Farm shop",
        "group": "animals", "base_score": 88,
        "filters": [
            '["tourism"="attraction"]["attraction"="animal"]',
            '["amenity"="animal_boarding"]',
            '["shop"="farm"]',
            '["tourism"="farm"]',
        ],
    },
    "zoo": {
        "label_de": "Zoo / Wildpark", "label_fr": "Zoo / Parc animalier",
        "label_lb": "Zoo / Déierepark", "label_en": "Zoo / Wildlife park",
        "group": "animals", "base_score": 92,
        "filters": [
            '["tourism"="zoo"]',
            '["attraction"="animal"]',
        ],
    },
    "horse": {
        "label_de": "Reiterhof / Ponys", "label_fr": "Centre équestre",
        "label_lb": "Päerdshaff",         "label_en": "Horse riding",
        "group": "animals", "base_score": 72,
        "filters": [
            '["leisure"="horse_riding"]',
            '["sport"="equestrian"]',
        ],
    },

    # ---------- Kultur & Lernen ----------
    "museum": {
        "label_de": "Museum", "label_fr": "Musée",
        "label_lb": "Musée",  "label_en": "Museum",
        "group": "culture", "base_score": 65,
        "filters": ['["tourism"="museum"]'],
    },
    "castle": {
        "label_de": "Burg / Schloss / Ruine", "label_fr": "Château / Ruine",
        "label_lb": "Buerg / Schlass / Ruinn", "label_en": "Castle / Ruin",
        "group": "culture", "base_score": 78,
        "filters": [
            '["historic"="castle"]',
            '["historic"="fort"]',
            '["historic"="ruins"]',
        ],
    },
    "library": {
        "label_de": "Bibliothek", "label_fr": "Bibliothèque",
        "label_lb": "Bibliothéik", "label_en": "Library",
        "group": "culture", "base_score": 60,
        "filters": ['["amenity"="library"]'],
    },
    "theatre_cinema": {
        "label_de": "Theater / Kino / Kulturzentrum", "label_fr": "Théâtre / Cinéma",
        "label_lb": "Theater / Kino",                  "label_en": "Theatre / Cinema",
        "group": "culture", "base_score": 58,
        "filters": [
            '["amenity"="theatre"]',
            '["amenity"="cinema"]',
            '["amenity"="arts_centre"]',
        ],
    },
    "science": {
        "label_de": "Science Center / Sternwarte", "label_fr": "Centre scientifique",
        "label_lb": "Science Center",              "label_en": "Science centre",
        "group": "culture", "base_score": 80,
        "filters": [
            '["tourism"="attraction"]["attraction"="science"]',
            '["man_made"="observatory"]',
        ],
    },

    # ---------- Sport & Schwimmen ----------
    "swimming": {
        "label_de": "Schwimmbad / Freibad", "label_fr": "Piscine",
        "label_lb": "Schwämm",              "label_en": "Swimming pool",
        "group": "sport", "base_score": 85,
        # Require a name — OSM Luxembourg has ~1800 unnamed private backyard
        # pools tagged `leisure=swimming_pool` that we do NOT want to expose.
        "require_name": True,
        "filters": [
            '["leisure"="swimming_pool"]',
            '["amenity"="public_bath"]',
            '["leisure"="water_park"]',
        ],
    },
    "ice_rink": {
        "label_de": "Eislaufbahn", "label_fr": "Patinoire",
        "label_lb": "Aisstadion",  "label_en": "Ice rink",
        "group": "sport", "base_score": 75,
        "filters": ['["leisure"="ice_rink"]'],
    },
    "climbing": {
        "label_de": "Klettern (Halle / Fels)", "label_fr": "Escalade",
        "label_lb": "Klammeren",                "label_en": "Climbing",
        "group": "sport", "base_score": 70,
        "filters": [
            '["sport"="climbing"]',
            '["leisure"="sports_centre"]["sport"="climbing"]',
        ],
    },
    "bowling_etc": {
        "label_de": "Bowling / Trampolinpark", "label_fr": "Bowling / Trampoline",
        "label_lb": "Bowling / Trampolinn",     "label_en": "Bowling / Trampoline",
        "group": "sport", "base_score": 72,
        "filters": [
            '["leisure"="bowling_alley"]',
            '["leisure"="trampoline_park"]',
            '["leisure"="amusement_arcade"]',
        ],
    },
    "theme_park": {
        "label_de": "Freizeitpark", "label_fr": "Parc d'attractions",
        "label_lb": "Fräizäitpark", "label_en": "Theme park",
        "group": "sport", "base_score": 95,
        "filters": ['["tourism"="theme_park"]'],
    },
}


# -------- Score rules: (osm_tag, value_regex_or_None, delta) --------
# Positive rules add to the base_score, negatives penalise.  `None` for
# value_regex means the presence of the tag is enough.
SCORE_RULES = [
    ("name",              None,               +5),
    ("website",           None,               +2),
    ("opening_hours",     None,               +2),
    ("wheelchair",        r"^(yes|designated)$", +4),
    ("toilets",           r"^yes$",           +4),
    # The POI *is* a toilet.  OSM spells this amenity=toilets — a key literally
    # named "amenity:toilets" does not exist, so the old rule never once fired.
    ("amenity",           r"^toilets$",       +4),
    ("drinking_water",    r"^yes$",           +3),
    ("shade",             r"^(yes|partial)$", +3),
    ("fee",               r"^no$",            +3),
    ("fee",               r"^yes$",           -3),
    ("playground:theme",  None,               +3),
    ("max_age",           None,               +2),
    # baby_feeding is commonly tagged "no".  Without a value check, a place that
    # states it has nowhere to feed a baby scored the same as one that has.
    ("baby_feeding",      r"^(yes|room|dedicated_room)$", +5),
    ("changing_table",    r"^yes$",           +5),
    ("access",            r"^(private|no|customers)$", -40),
]


NAME_KEYS = [
    "name:lb", "name:de", "name:fr", "name",
    "official_name", "loc_name", "alt_name",
]


CATEGORY_ORDER = list(CATEGORIES.keys())
