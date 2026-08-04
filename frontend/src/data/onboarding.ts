/**
 * Onboarding data: personas, interests, needs — with i18n labels for EN/DE/FR.
 *
 * The user profile shape stored in AppContext:
 *
 *   {
 *     persona: 'family' | 'young_adult' | 'couple' | 'senior' | 'tourist' | 'skipped',
 *     childAgeGroups: string[]        // subset of CHILD_AGE_GROUPS ids
 *     interests: string[]             // subset of INTEREST_TAGS ids
 *     needs: string[]                 // subset of NEED_TAGS ids
 *     completedAt: number | null      // epoch ms, null if user skipped
 *   }
 *
 * The AppContext exposes `hasOnboarded` = has visited the flow at least once
 * (whether the user finished or skipped).
 */

import type { Lang } from "@/src/data/places";

// ---------------------------------------------------------------------------
// Personas
// ---------------------------------------------------------------------------

export type PersonaId =
  | "family"
  | "young_adult"
  | "couple"
  | "senior"
  | "tourist"
  | "skipped";

type LocalizedString = Record<Lang, string>;

export type Persona = {
  id: PersonaId;
  icon: string;                   // Ionicons name
  labels: LocalizedString;
  descriptions: LocalizedString;
  askChildAges?: boolean;         // only true for 'family'
  defaultInterests: string[];     // pre-checked interests for this persona
};

export const PERSONAS: Persona[] = [
  {
    id: "family",
    icon: "people-outline",
    askChildAges: true,
    labels: {
      en: "Family with kids",
      de: "Familie mit Kindern",
      fr: "Famille avec enfants",
    },
    descriptions: {
      en: "Playgrounds, animal parks, workshops, family-friendly food.",
      de: "Spielplätze, Tierparks, Workshops, kinderfreundliches Essen.",
      fr: "Aires de jeux, parcs animaliers, ateliers, restos famille.",
    },
    defaultInterests: ["playgrounds", "nature", "animals", "workshops", "culture_kids"],
  },
  {
    id: "young_adult",
    icon: "sparkles-outline",
    labels: {
      en: "Young adult",
      de: "Junger Erwachsener",
      fr: "Jeune adulte",
    },
    descriptions: {
      en: "Nightlife, concerts, fine dining, wine, festivals & sports.",
      de: "Nightlife, Konzerte, Feinschmecker, Wein, Festivals & Sport.",
      fr: "Nightlife, concerts, gastronomie, vins, festivals et sport.",
    },
    defaultInterests: ["nightlife", "concerts", "fine_dining", "festivals", "sports"],
  },
  {
    id: "couple",
    icon: "heart-outline",
    labels: {
      en: "Couple / Date nights",
      de: "Paar / Date-Nights",
      fr: "En couple / Soirées",
    },
    descriptions: {
      en: "Romantic restaurants, wine tastings, culture, weekend trips.",
      de: "Romantische Restaurants, Weinproben, Kultur, Wochenendtrips.",
      fr: "Restaurants romantiques, œnologie, culture, week-ends.",
    },
    defaultInterests: ["fine_dining", "wine", "culture", "wellness", "nature"],
  },
  {
    id: "senior",
    icon: "leaf-outline",
    labels: {
      en: "Senior / Quiet-seeker",
      de: "Senior / Ruhesucher",
      fr: "Senior / Amateur de calme",
    },
    descriptions: {
      en: "Museums, gardens, gentle walks, cafés, accessible venues.",
      de: "Museen, Gärten, ruhige Spaziergänge, Cafés, barrierefrei.",
      fr: "Musées, jardins, promenades, cafés, lieux accessibles.",
    },
    defaultInterests: ["culture", "nature", "wellness", "food"],
  },
  {
    id: "tourist",
    icon: "airplane-outline",
    labels: {
      en: "Tourist / Short visit",
      de: "Tourist / Kurzbesuch",
      fr: "Touriste / Court séjour",
    },
    descriptions: {
      en: "Landmarks, top attractions, must-see events, guided tours.",
      de: "Wahrzeichen, Top-Attraktionen, Must-see-Events, Führungen.",
      fr: "Monuments, incontournables, événements, visites guidées.",
    },
    defaultInterests: ["culture", "landmarks", "festivals", "food", "nature"],
  },
];

// ---------------------------------------------------------------------------
// Interests (used by everyone, filtered by persona)
// ---------------------------------------------------------------------------

export type InterestTag = {
  id: string;
  icon: string;
  labels: LocalizedString;
  personas: PersonaId[];          // which personas typically care about this
};

export const INTEREST_TAGS: InterestTag[] = [
  { id: "playgrounds",  icon: "happy-outline",           personas: ["family"],
    labels: { en: "Playgrounds", de: "Spielplätze", fr: "Aires de jeux" } },
  { id: "animals",      icon: "paw-outline",             personas: ["family", "tourist"],
    labels: { en: "Animals & farms", de: "Tiere & Bauernhöfe", fr: "Animaux & fermes" } },
  { id: "nature",       icon: "leaf-outline",            personas: ["family", "young_adult", "couple", "senior", "tourist"],
    labels: { en: "Nature & hikes", de: "Natur & Wandern", fr: "Nature & randos" } },
  { id: "workshops",    icon: "construct-outline",       personas: ["family"],
    labels: { en: "Workshops", de: "Workshops", fr: "Ateliers" } },
  { id: "culture_kids", icon: "color-palette-outline",   personas: ["family"],
    labels: { en: "Kids' culture", de: "Kinder-Kultur", fr: "Culture enfants" } },
  { id: "culture",      icon: "library-outline",         personas: ["young_adult", "couple", "senior", "tourist"],
    labels: { en: "Museums & arts", de: "Museen & Kunst", fr: "Musées & arts" } },
  { id: "landmarks",    icon: "business-outline",        personas: ["tourist", "senior"],
    labels: { en: "Landmarks", de: "Wahrzeichen", fr: "Monuments" } },
  { id: "festivals",    icon: "musical-notes-outline",   personas: ["young_adult", "couple", "tourist"],
    labels: { en: "Festivals", de: "Festivals", fr: "Festivals" } },
  { id: "concerts",     icon: "mic-outline",             personas: ["young_adult", "couple"],
    labels: { en: "Concerts & live music", de: "Konzerte & Live-Musik", fr: "Concerts & live" } },
  { id: "nightlife",    icon: "moon-outline",            personas: ["young_adult"],
    labels: { en: "Nightlife & bars", de: "Nightlife & Bars", fr: "Nightlife & bars" } },
  { id: "fine_dining",  icon: "restaurant-outline",      personas: ["young_adult", "couple"],
    labels: { en: "Fine dining", de: "Feinschmecker", fr: "Gastronomie" } },
  { id: "food",         icon: "fast-food-outline",       personas: ["family", "young_adult", "couple", "senior", "tourist"],
    labels: { en: "Food & markets", de: "Essen & Märkte", fr: "Cuisine & marchés" } },
  { id: "wine",         icon: "wine-outline",            personas: ["young_adult", "couple", "senior"],
    labels: { en: "Wine & vineyards", de: "Wein & Winzer", fr: "Vin & vignobles" } },
  { id: "sports",       icon: "bicycle-outline",         personas: ["young_adult", "family"],
    labels: { en: "Sport & outdoors", de: "Sport & Outdoor", fr: "Sport & plein air" } },
  { id: "wellness",     icon: "flower-outline",          personas: ["couple", "senior"],
    labels: { en: "Wellness & spa", de: "Wellness & Spa", fr: "Bien-être & spa" } },
  { id: "shopping",     icon: "bag-handle-outline",      personas: ["young_adult", "couple", "tourist"],
    labels: { en: "Shopping", de: "Shopping", fr: "Shopping" } },
];

// ---------------------------------------------------------------------------
// Deal-breaker / needs
// ---------------------------------------------------------------------------

export type NeedTag = {
  id: string;
  icon: string;
  labels: LocalizedString;
};

export const NEED_TAGS: NeedTag[] = [
  { id: "wheelchair",     icon: "accessibility-outline",
    labels: { en: "Wheelchair accessible", de: "Rollstuhlgerecht", fr: "Accessible PMR" } },
  { id: "sensory",        icon: "ear-outline",
    labels: { en: "Sensory friendly", de: "Reizarm / sensor-freundlich", fr: "Sensoriellement adapté" } },
  { id: "free_parking",   icon: "car-outline",
    labels: { en: "Free parking", de: "Kostenlos parken", fr: "Parking gratuit" } },
  { id: "free_entry",     icon: "pricetag-outline",
    labels: { en: "Free entry", de: "Kostenloser Eintritt", fr: "Entrée gratuite" } },
  { id: "stroller",       icon: "walk-outline",
    labels: { en: "Stroller-friendly", de: "Kinderwagen-tauglich", fr: "Adapté poussette" } },
  { id: "dogs_allowed",   icon: "paw-outline",
    labels: { en: "Dogs welcome", de: "Hunde willkommen", fr: "Chiens bienvenus" } },
  { id: "veggie_options", icon: "leaf-outline",
    labels: { en: "Vegetarian/vegan food", de: "Vegetarisch/vegan", fr: "Options végé/vegan" } },
];

// ---------------------------------------------------------------------------
// Child age groups
// ---------------------------------------------------------------------------

export type ChildAgeGroup = {
  id: string;
  labels: LocalizedString;
  min: number;
  max: number;
};

export const CHILD_AGE_GROUPS: ChildAgeGroup[] = [
  { id: "0-3",  min: 0, max: 3,  labels: { en: "0-3 (baby & toddler)",   de: "0-3 (Baby & Kleinkind)",     fr: "0-3 (bébé)"       } },
  { id: "4-8",  min: 4, max: 8,  labels: { en: "4-8 (preschool/school)", de: "4-8 (Kita/Grundschule)",     fr: "4-8 (école)"      } },
  { id: "9-14", min: 9, max: 14, labels: { en: "9-14 (tweens)",          de: "9-14 (Teens)",               fr: "9-14 (préados)"   } },
  { id: "15+",  min: 15, max: 18,labels: { en: "15+ (teenagers)",        de: "15+ (Jugendliche)",          fr: "15+ (ados)"       } },
];

// ---------------------------------------------------------------------------
// Preferred cantons (Luxembourg's 12 cantons + "everywhere")
// ---------------------------------------------------------------------------
export type CantonOption = {
  id: string;         // matches the `canton` field on ApiEvent
  labels: LocalizedString;
};

export const CANTON_OPTIONS: CantonOption[] = [
  { id: "Luxembourg",         labels: { en: "Luxembourg (city)", de: "Luxembourg (Stadt)", fr: "Luxembourg (ville)" } },
  { id: "Esch-sur-Alzette",   labels: { en: "Esch-sur-Alzette",  de: "Esch-sur-Alzette",   fr: "Esch-sur-Alzette" } },
  { id: "Diekirch",           labels: { en: "Diekirch",          de: "Diekirch",           fr: "Diekirch" } },
  { id: "Clervaux",           labels: { en: "Clervaux",          de: "Clervaux",           fr: "Clervaux" } },
  { id: "Vianden",            labels: { en: "Vianden",           de: "Vianden",            fr: "Vianden" } },
  { id: "Wiltz",              labels: { en: "Wiltz",             de: "Wiltz",              fr: "Wiltz" } },
  { id: "Redange",            labels: { en: "Redange",           de: "Redange",            fr: "Redange" } },
  { id: "Capellen",           labels: { en: "Capellen",          de: "Capellen",           fr: "Capellen" } },
  { id: "Mersch",             labels: { en: "Mersch",            de: "Mersch",             fr: "Mersch" } },
  { id: "Grevenmacher",       labels: { en: "Grevenmacher",      de: "Grevenmacher",       fr: "Grevenmacher" } },
  { id: "Echternach",         labels: { en: "Echternach",        de: "Echternach",         fr: "Echternach" } },
  { id: "Remich",             labels: { en: "Remich",            de: "Remich",             fr: "Remich" } },
];

// ---------------------------------------------------------------------------
// Budget bands (per adult ticket)
// ---------------------------------------------------------------------------
export type BudgetOption = {
  id: string;
  max: number | null;           // null = no limit
  labels: LocalizedString;
  icon: string;
};

export const BUDGET_OPTIONS: BudgetOption[] = [
  { id: "free",    max: 0,    icon: "gift-outline",       labels: { en: "Free only",      de: "Nur kostenlos",  fr: "Uniquement gratuit" } },
  { id: "cheap",   max: 15,   icon: "wallet-outline",     labels: { en: "Up to €15",      de: "Bis 15 €",       fr: "Jusqu'à 15 €" } },
  { id: "medium",  max: 30,   icon: "card-outline",       labels: { en: "Up to €30",      de: "Bis 30 €",       fr: "Jusqu'à 30 €" } },
  { id: "any",     max: null, icon: "infinite-outline",   labels: { en: "Any budget",     de: "Egal",           fr: "Peu importe" } },
];

// ---------------------------------------------------------------------------
// Wizard step copy
// ---------------------------------------------------------------------------

export const ONBOARDING_COPY = {
  welcomeTitle: {
    en: "Welcome to Wat Elo?",
    de: "Willkommen bei Wat Elo?",
    fr: "Bienvenue chez Wat Elo?",
  },
  welcomeSubtitle: {
    en: "Answer 3 quick questions so we can suggest the right places and events for you.",
    de: "Beantworte 3 kurze Fragen, damit wir dir die passenden Orte & Events zeigen.",
    fr: "Réponds à 3 questions rapides pour voir les activités adaptées.",
  },
  personaTitle:  { en: "Who are you?",       de: "Wer bist du?",      fr: "Qui es-tu ?" },
  personaSub:    { en: "Pick the one that fits best.",
                    de: "Wähle, was am besten passt.",
                    fr: "Choisis le profil qui te correspond." },
  ageTitle:      { en: "How old are the kids?", de: "Wie alt sind die Kinder?", fr: "L'âge des enfants ?" },
  ageSub:        { en: "Pick all that apply.",  de: "Mehrfachauswahl möglich.",  fr: "Sélection multiple possible." },
  interestsTitle:{ en: "What interests you?",   de: "Was interessiert dich?",    fr: "Qu'est-ce qui t'intéresse ?" },
  interestsSub:  { en: "Pick 3 or more.",       de: "Wähle 3 oder mehr.",         fr: "Choisis-en au moins 3." },
  needsTitle:    { en: "Anything must-have?",   de: "Was ist dir wichtig?",       fr: "Des besoins spécifiques ?" },
  needsSub:      { en: "Optional — helps us filter out mismatches.",
                    de: "Optional — hilft, unpassende Vorschläge auszublenden.",
                    fr: "Optionnel — pour filtrer les résultats." },
  cantonsTitle:  { en: "Where do you spend most time?",
                    de: "Wo bist du meistens unterwegs?",
                    fr: "Où passes-tu le plus de temps ?" },
  cantonsSub:    { en: "Skip to see events all over Luxembourg.",
                    de: "Überspringen, um Events aus ganz Luxemburg zu sehen.",
                    fr: "Passer pour voir tous les événements." },
  budgetTitle:   { en: "What's your comfort zone?",
                    de: "Was ist dein Budget?",
                    fr: "Quel budget préfères-tu ?" },
  budgetSub:     { en: "Per adult ticket. We'll rank cheaper options higher.",
                    de: "Pro Erwachsenen-Ticket. Günstigere Optionen werden bevorzugt.",
                    fr: "Par billet adulte. Les moins chers seront priorisés." },
  doneTitle:     { en: "You're all set!",       de: "Fertig!",                    fr: "C'est parti !" },
  doneSub:       { en: "You can change any of this later in your Profile.",
                    de: "Du kannst das jederzeit in deinem Profil ändern.",
                    fr: "Modifiable à tout moment dans ton profil." },
  skip:          { en: "Skip for now",          de: "Später einrichten",           fr: "Ignorer pour l'instant" },
  skipWarnTitle: { en: "Show me everything?",   de: "Alles anzeigen?",             fr: "Tout afficher ?" },
  skipWarnBody:  {
    en: "Without a profile we cannot personalise your feed. Suggested content may not match your interests.",
    de: "Ohne Profil können wir deinen Feed nicht personalisieren. Die vorgeschlagenen Inhalte entsprechen möglicherweise nicht deinen Interessen.",
    fr: "Sans profil, nous ne pouvons pas personnaliser ton flux. Les suggestions pourraient ne pas te correspondre.",
  },
  skipConfirm:   { en: "Skip anyway",           de: "Trotzdem überspringen",       fr: "Ignorer quand même" },
  cancel:        { en: "Cancel",                de: "Zurück",                      fr: "Annuler" },
  next:          { en: "Continue",              de: "Weiter",                       fr: "Continuer" },
  back:          { en: "Back",                  de: "Zurück",                       fr: "Précédent" },
  finish:        { en: "Show me events",        de: "Los geht's",                   fr: "C'est parti" },
} as const;
