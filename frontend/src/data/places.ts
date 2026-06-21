// Static seed data for Luxembourg family activities.
// Translations are provided per language; pick via getPlace(id, lang).

export type Lang = "en" | "de" | "fr";

export type LocalizedString = Record<Lang, string>;

export type Canton =
  | "Capellen"
  | "Clervaux"
  | "Diekirch"
  | "Echternach"
  | "Esch-sur-Alzette"
  | "Grevenmacher"
  | "Luxembourg"
  | "Mersch"
  | "Redange"
  | "Remich"
  | "Vianden"
  | "Wiltz";

export const CANTONS: Canton[] = [
  "Capellen",
  "Clervaux",
  "Diekirch",
  "Echternach",
  "Esch-sur-Alzette",
  "Grevenmacher",
  "Luxembourg",
  "Mersch",
  "Redange",
  "Remich",
  "Vianden",
  "Wiltz",
];

export type Place = {
  id: number;
  title: LocalizedString;
  short: LocalizedString;
  type: "Outdoor" | "Indoor" | "Event" | "Educational";
  age: string;
  ageMin: number;
  ageMax: number;
  distanceKm: number;
  town: string;
  canton: Canton;
  category: string[];
  weatherFit: LocalizedString;
  image: string;
  date: LocalizedString;
  time: string;
  priceAdult: number;
  priceChild: number;
  priceLabel: LocalizedString;
  accessibility: LocalizedString;
  description: LocalizedString;
  lat: number;
  lng: number;
  bookable: boolean;
  rating: number;
  wheelchair?: boolean;
  sensoryFriendly?: boolean;
  freeParking?: boolean;
};

export const PLACES: Place[] = [
  {
    id: 1,
    title: {
      en: "Visit the Farm A Schmatten",
      de: "Besuch auf dem Bauernhof A Schmatten",
      fr: "Visite de la Ferme A Schmatten",
    },
    short: {
      en: "Meet animals, play and discover nature.",
      de: "Tiere treffen, spielen und Natur entdecken.",
      fr: "Rencontrer les animaux, jouer et explorer la nature.",
    },
    type: "Outdoor",
    age: "2-10",
    ageMin: 2,
    ageMax: 10,
    distanceKm: 2.4,
    town: "Walferdange",
    canton: "Luxembourg",
    category: ["Animals", "Nature"],
    weatherFit: {
      en: "Sunny & 18 degrees",
      de: "Sonnig & 18 Grad",
      fr: "Ensoleille & 18 degres",
    },
    image:
      "https://images.unsplash.com/photo-1500595046743-cd271d694d30?auto=format&fit=crop&w=1200&q=80",
    date: { en: "Open daily", de: "Taeglich offen", fr: "Ouvert tous les jours" },
    time: "10:00 - 18:00",
    priceAdult: 6,
    priceChild: 4,
    priceLabel: {
      en: "EUR 6 / adult - EUR 4 / child",
      de: "6 EUR / Erw. - 4 EUR / Kind",
      fr: "6 EUR / adulte - 4 EUR / enfant",
    },
    accessibility: {
      en: "Stroller friendly",
      de: "Kinderwagenfreundlich",
      fr: "Accessible poussette",
    },
    description: {
      en: "A friendly educational farm where kids can meet animals, explore nature and play in the big outdoor area.",
      de: "Ein freundlicher Lern-Bauernhof, wo Kinder Tiere kennenlernen, die Natur erkunden und im grossen Aussenbereich spielen.",
      fr: "Une ferme pedagogique conviviale ou les enfants rencontrent des animaux et explorent la nature.",
    },
    lat: 49.6608,
    lng: 6.1336,
    bookable: true,
    rating: 4.8,
  },
  {
    id: 2,
    title: {
      en: "Mudam Family Workshop",
      de: "Mudam Familien-Workshop",
      fr: "Atelier Famille Mudam",
    },
    short: {
      en: "Creative workshop for kids and parents.",
      de: "Kreativer Workshop fuer Kinder und Eltern.",
      fr: "Atelier creatif pour enfants et parents.",
    },
    type: "Indoor",
    age: "4-12",
    ageMin: 4,
    ageMax: 12,
    distanceKm: 1.8,
    town: "Luxembourg City",
    canton: "Luxembourg",
    category: ["Culture", "Workshops"],
    weatherFit: {
      en: "Perfect for rainy afternoons",
      de: "Perfekt fuer regnerische Nachmittage",
      fr: "Parfait pour les apres-midi pluvieux",
    },
    image:
      "https://images.unsplash.com/photo-1607453998774-d533f65dac99?auto=format&fit=crop&w=1200&q=80",
    date: {
      en: "Saturday, 25 May",
      de: "Samstag, 25. Mai",
      fr: "Samedi 25 mai",
    },
    time: "15:00 - 16:30",
    priceAdult: 0,
    priceChild: 0,
    priceLabel: {
      en: "Free with museum ticket",
      de: "Gratis mit Museumsticket",
      fr: "Gratuit avec billet musee",
    },
    accessibility: {
      en: "Barrier-free",
      de: "Barrierefrei",
      fr: "Sans barrieres",
    },
    description: {
      en: "Hands-on art activities designed for families, with rotating themes inspired by current exhibitions.",
      de: "Praktische Kunstaktivitaeten fuer Familien, mit wechselnden Themen inspiriert von aktuellen Ausstellungen.",
      fr: "Activites artistiques pratiques pour les familles, themes inspires des expositions en cours.",
    },
    lat: 49.6411,
    lng: 6.1417,
    bookable: true,
    rating: 4.6,
  },
  {
    id: 3,
    title: {
      en: "Street Food Festival Luxembourg",
      de: "Street Food Festival Luxemburg",
      fr: "Festival Street Food Luxembourg",
    },
    short: {
      en: "Tasty food, music and activities.",
      de: "Leckeres Essen, Musik und Aktivitaeten.",
      fr: "Cuisine savoureuse, musique et animations.",
    },
    type: "Event",
    age: "All",
    ageMin: 0,
    ageMax: 99,
    distanceKm: 3.1,
    town: "Kirchberg",
    canton: "Luxembourg",
    category: ["Festivals"],
    weatherFit: {
      en: "Best on dry evenings",
      de: "Am besten an trockenen Abenden",
      fr: "Mieux par soirees seches",
    },
    image:
      "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=1200&q=80",
    date: { en: "Today", de: "Heute", fr: "Aujourd'hui" },
    time: "11:00 - 22:00",
    priceAdult: 0,
    priceChild: 0,
    priceLabel: {
      en: "Free entry",
      de: "Eintritt frei",
      fr: "Entree libre",
    },
    accessibility: {
      en: "Step-free access",
      de: "Stufenloser Zugang",
      fr: "Acces sans marches",
    },
    description: {
      en: "A lively family-friendly food festival with street food stalls, music and open public spaces.",
      de: "Ein lebendiges familienfreundliches Essensfestival mit Streetfood-Staenden, Musik und offenen Plaetzen.",
      fr: "Un festival convivial avec stands de street food, musique et espaces ouverts.",
    },
    lat: 49.6308,
    lng: 6.1620,
    bookable: false,
    rating: 4.4,
  },
  {
    id: 4,
    title: {
      en: "Kizou Indoor Play",
      de: "Kizou Indoor Spielplatz",
      fr: "Kizou Aire de Jeux Couverte",
    },
    short: {
      en: "Indoor playground for all ages.",
      de: "Indoor-Spielplatz fuer alle Altersgruppen.",
      fr: "Aire de jeux couverte pour tous.",
    },
    type: "Indoor",
    age: "0-10",
    ageMin: 0,
    ageMax: 10,
    distanceKm: 2.0,
    town: "Strassen",
    canton: "Luxembourg",
    category: ["Playgrounds"],
    weatherFit: {
      en: "Great when it rains",
      de: "Super bei Regen",
      fr: "Ideal sous la pluie",
    },
    image:
      "https://images.unsplash.com/photo-1597524678053-faf08e5e1aff?auto=format&fit=crop&w=1200&q=80",
    date: { en: "Open daily", de: "Taeglich offen", fr: "Ouvert tous les jours" },
    time: "09:30 - 18:30",
    priceAdult: 0,
    priceChild: 12,
    priceLabel: {
      en: "EUR 12 / child",
      de: "12 EUR / Kind",
      fr: "12 EUR / enfant",
    },
    accessibility: {
      en: "Stroller parking",
      de: "Kinderwagen-Parkplatz",
      fr: "Parking poussettes",
    },
    description: {
      en: "An energetic indoor play zone with soft play, climbing areas and a cafe for parents.",
      de: "Eine energiegeladene Indoor-Spielzone mit Soft-Play, Kletterbereich und Cafe fuer Eltern.",
      fr: "Une zone de jeux interieure dynamique avec espaces souples, escalade et cafe pour parents.",
    },
    lat: 49.6181,
    lng: 6.0780,
    bookable: true,
    rating: 4.5,
  },
  {
    id: 5,
    title: {
      en: "Natur Musee",
      de: "Naturmuseum",
      fr: "Musee National d'Histoire Naturelle",
    },
    short: {
      en: "Interactive museum about nature.",
      de: "Interaktives Museum ueber die Natur.",
      fr: "Musee interactif sur la nature.",
    },
    type: "Educational",
    age: "4-12",
    ageMin: 4,
    ageMax: 12,
    distanceKm: 1.6,
    town: "Luxembourg City",
    canton: "Luxembourg",
    category: ["Culture", "Nature"],
    weatherFit: {
      en: "Excellent indoor backup",
      de: "Ausgezeichnete Indoor-Option",
      fr: "Excellent plan B en interieur",
    },
    image:
      "https://images.unsplash.com/photo-1503424886307-b090341d25d1?auto=format&fit=crop&w=1200&q=80",
    date: { en: "Open daily", de: "Taeglich offen", fr: "Ouvert tous les jours" },
    time: "10:00 - 18:00",
    priceAdult: 5,
    priceChild: 0,
    priceLabel: {
      en: "EUR 5 / adult - kids free",
      de: "5 EUR / Erw. - Kinder gratis",
      fr: "5 EUR / adulte - enfants gratuits",
    },
    accessibility: {
      en: "Barrier-free",
      de: "Barrierefrei",
      fr: "Sans barrieres",
    },
    description: {
      en: "Interactive exhibitions about wildlife, geology and ecosystems with plenty for curious children.",
      de: "Interaktive Ausstellungen ueber Tierwelt, Geologie und Oekosysteme mit viel fuer neugierige Kinder.",
      fr: "Expositions interactives sur la faune, la geologie et les ecosystemes pour enfants curieux.",
    },
    lat: 49.6126,
    lng: 6.1399,
    bookable: true,
    rating: 4.7,
  },
  {
    id: 6,
    title: {
      en: "Parc Merveilleux Bettembourg",
      de: "Parc Merveilleux Bettemburg",
      fr: "Parc Merveilleux Bettembourg",
    },
    short: {
      en: "Fairytale park with animals and rides.",
      de: "Maerchenpark mit Tieren und Fahrgeschaeften.",
      fr: "Parc de contes avec animaux et manages.",
    },
    type: "Outdoor",
    age: "2-12",
    ageMin: 2,
    ageMax: 12,
    distanceKm: 14.0,
    town: "Bettembourg",
    canton: "Esch-sur-Alzette",
    category: ["Animals", "Nature", "Playgrounds"],
    weatherFit: {
      en: "Best on sunny days",
      de: "Am besten an sonnigen Tagen",
      fr: "Au mieux par temps ensoleille",
    },
    image:
      "https://images.unsplash.com/photo-1502086223501-7ea6ecd79368?auto=format&fit=crop&w=1200&q=80",
    date: {
      en: "Open daily until October",
      de: "Taeglich offen bis Oktober",
      fr: "Ouvert tous les jours jusqu'en octobre",
    },
    time: "10:00 - 19:00",
    priceAdult: 14,
    priceChild: 11,
    priceLabel: {
      en: "EUR 14 / adult - EUR 11 / child",
      de: "14 EUR / Erw. - 11 EUR / Kind",
      fr: "14 EUR / adulte - 11 EUR / enfant",
    },
    accessibility: {
      en: "Stroller friendly",
      de: "Kinderwagenfreundlich",
      fr: "Accessible poussette",
    },
    description: {
      en: "A magical adventure park combining fairytale scenes, animal enclosures, playgrounds and a small train.",
      de: "Ein magischer Abenteuerpark mit Maerchenszenen, Tiergehegen, Spielplaetzen und einer kleinen Bahn.",
      fr: "Un parc d'aventure magique avec contes, enclos d'animaux, aires de jeux et un petit train.",
    },
    lat: 49.5179,
    lng: 6.0922,
    bookable: true,
    rating: 4.9,
  },
  {
    id: 7,
    title: {
      en: "Mullerthal Hike for Kids",
      de: "Mullerthal Wanderung fuer Kinder",
      fr: "Randonnee Mullerthal pour Enfants",
    },
    short: {
      en: "Family-friendly trail in the Little Switzerland.",
      de: "Familienfreundlicher Pfad in der kleinen Schweiz.",
      fr: "Sentier familial dans la petite Suisse.",
    },
    type: "Outdoor",
    age: "5-12",
    ageMin: 5,
    ageMax: 12,
    distanceKm: 28.0,
    town: "Echternach",
    canton: "Echternach",
    category: ["Nature"],
    weatherFit: {
      en: "Cool forest, great on hot days",
      de: "Kuehler Wald, ideal bei Hitze",
      fr: "Foret fraiche, ideale par chaleur",
    },
    image:
      "https://images.unsplash.com/photo-1551632811-561732d1e306?auto=format&fit=crop&w=1200&q=80",
    date: { en: "Anytime", de: "Jederzeit", fr: "A tout moment" },
    time: "08:00 - sunset",
    priceAdult: 0,
    priceChild: 0,
    priceLabel: { en: "Free", de: "Kostenlos", fr: "Gratuit" },
    accessibility: {
      en: "Hiking shoes recommended",
      de: "Wanderschuhe empfohlen",
      fr: "Chaussures de randonnee recommandees",
    },
    description: {
      en: "Discover dramatic sandstone rocks, mossy forest and waterfalls on a gentle loop tailored for kids.",
      de: "Entdecke dramatische Sandsteinfelsen, moosigen Wald und Wasserfaelle auf einer sanften Schleife.",
      fr: "Decouvrez des rochers de gres, foret moussue et cascades sur une boucle douce.",
    },
    lat: 49.7333,
    lng: 6.4167,
    bookable: false,
    rating: 4.8,
  },
  {
    id: 8,
    title: {
      en: "Aquasud Swimming Pool",
      de: "Aquasud Schwimmbad",
      fr: "Piscine Aquasud",
    },
    short: {
      en: "Family pool with slides and shallow areas.",
      de: "Familienbad mit Rutschen und flachen Bereichen.",
      fr: "Piscine familiale avec toboggans.",
    },
    type: "Indoor",
    age: "0-12",
    ageMin: 0,
    ageMax: 12,
    distanceKm: 18.0,
    town: "Oberkorn",
    canton: "Esch-sur-Alzette",
    category: ["Water"],
    weatherFit: {
      en: "Any weather",
      de: "Bei jedem Wetter",
      fr: "Par tous les temps",
    },
    image:
      "https://images.unsplash.com/photo-1576013551627-0cc20b96c2a7?auto=format&fit=crop&w=1200&q=80",
    date: { en: "Open daily", de: "Taeglich offen", fr: "Ouvert tous les jours" },
    time: "08:00 - 21:00",
    priceAdult: 5.5,
    priceChild: 3.5,
    priceLabel: {
      en: "EUR 5.5 / adult - EUR 3.5 / child",
      de: "5,50 EUR / Erw. - 3,50 EUR / Kind",
      fr: "5,50 EUR / adulte - 3,50 EUR / enfant",
    },
    accessibility: {
      en: "Lift available",
      de: "Aufzug vorhanden",
      fr: "Ascenseur disponible",
    },
    description: {
      en: "Modern aquatic centre with a kids lagoon, slides, wave pool and a heated outdoor area in summer.",
      de: "Modernes Schwimmzentrum mit Kinderlagune, Rutschen, Wellenbad und beheiztem Aussenbereich.",
      fr: "Centre aquatique moderne avec lagune enfants, toboggans et zone exterieure chauffee.",
    },
    lat: 49.5106,
    lng: 5.9008,
    bookable: true,
    rating: 4.6,
  },
];

export const CATEGORIES = [
  "Animals",
  "Culture",
  "Playgrounds",
  "Water",
  "Nature",
  "Workshops",
  "Festivals",
] as const;

export const AGE_OPTIONS = ["0-3", "4-6", "7-12", "All"] as const;
export const TYPE_OPTIONS = ["Indoor", "Outdoor", "All"] as const;
export const DATE_OPTIONS = ["Today", "This weekend", "Next 7 days", "Anytime"] as const;
