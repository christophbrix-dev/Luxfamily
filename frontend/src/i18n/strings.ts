// Tiny translation dictionary; no runtime dep on i18next to keep the bundle lean.
import type { Lang } from "@/src/data/places";

type Dict = Record<string, Record<Lang, string>>;

export const STRINGS: Dict = {
  appTitle: { en: "Wat Elo?", de: "Wat Elo?", fr: "Wat Elo?" },
  goodMorning: { en: "Good morning!", de: "Guten Morgen!", fr: "Bonjour !" },
  goodAfternoon: { en: "Good afternoon!", de: "Guten Tag!", fr: "Bon après-midi !" },
  goodEvening: { en: "Good evening!", de: "Guten Abend!", fr: "Bonsoir !" },
  ideasForToday: {
    en: "Here are ideas for today",
    de: "Hier sind Ideen für heute",
    fr: "Voici des idées pour aujourd'hui",
  },
  home: { en: "Home", de: "Start", fr: "Accueil" },
  explore: { en: "Explore", de: "Entdecken", fr: "Explorer" },
  saved: { en: "Saved", de: "Favoriten", fr: "Favoris" },
  calendar: { en: "Calendar", de: "Kalender", fr: "Agenda" },
  profile: { en: "Profile", de: "Profil", fr: "Profil" },
  search: {
    en: "Search for places, events...",
    de: "Suche Orte, Events...",
    fr: "Chercher lieux, événements...",
  },
  nearYou: { en: "Near you", de: "In deiner Nähe", fr: "Près de vous" },
  seeAll: { en: "See all", de: "Alle anzeigen", fr: "Voir tout" },
  filter: { en: "Filter", de: "Filter", fr: "Filtres" },
  reset: { en: "Reset", de: "Zurücksetzen", fr: "Réinitialiser" },
  age: { en: "Age", de: "Alter", fr: "Âge" },
  indoorOutdoor: {
    en: "Indoor / Outdoor",
    de: "Drinnen / Draußen",
    fr: "Intérieur / Extérieur",
  },
  category: { en: "Category", de: "Kategorie", fr: "Catégorie" },
  date: { en: "Date", de: "Datum", fr: "Date" },
  showResults: { en: "Show results", de: "Ergebnisse zeigen", fr: "Voir les résultats" },
  places: { en: "Places", de: "Orte", fr: "Lieux" },
  events: { en: "Events", de: "Events", fr: "Événements" },
  itineraries: { en: "Itineraries", de: "Routen", fr: "Itinéraires" },
  thisWeekend: { en: "This weekend", de: "Dieses Wochenende", fr: "Ce week-end" },
  next7Days: { en: "Next 7 days", de: "Nächste 7 Tage", fr: "7 prochains jours" },
  june: { en: "June", de: "Juni", fr: "Juin" },
  myAccount: { en: "My account", de: "Mein Konto", fr: "Mon compte" },
  familyInLuxembourg: {
    en: "Family in Luxembourg",
    de: "Familie in Luxemburg",
    fr: "Famille au Luxembourg",
  },
  preferencesFilters: {
    en: "Preferences & filters",
    de: "Einstellungen & Filter",
    fr: "Préférences & filtres",
  },
  subscription: { en: "Subscription", de: "Abonnement", fr: "Abonnement" },
  savedInterests: {
    en: "Saved interests",
    de: "Gespeicherte Interessen",
    fr: "Centres d'intérêt",
  },
  language: { en: "Language", de: "Sprache", fr: "Langue" },
  signOut: { en: "Sign out", de: "Abmelden", fr: "Se déconnecter" },
  openInMaps: { en: "Open in Maps", de: "In Karten öffnen", fr: "Ouvrir dans Maps" },
  save: { en: "Save", de: "Speichern", fr: "Enregistrer" },
  unsave: { en: "Saved", de: "Gespeichert", fr: "Enregistré" },
  about: { en: "About", de: "Über", fr: "À propos" },
  location: { en: "Location", de: "Standort", fr: "Lieu" },
  fromYou: { en: "from you", de: "von dir", fr: "de vous" },
  greatForToday: {
    en: "Great for today",
    de: "Perfekt für heute",
    fr: "Parfait pour aujourd'hui",
  },
  bookNow: { en: "Book now", de: "Jetzt buchen", fr: "Réserver" },
  bookActivity: { en: "Book activity", de: "Aktivität buchen", fr: "Réserver l'activité" },
  yourBooking: { en: "Your booking", de: "Deine Buchung", fr: "Votre réservation" },
  selectDate: { en: "Select date", de: "Datum wählen", fr: "Choisir la date" },
  numAdults: { en: "Adults", de: "Erwachsene", fr: "Adultes" },
  numChildren: { en: "Children", de: "Kinder", fr: "Enfants" },
  total: { en: "Total", de: "Gesamt", fr: "Total" },
  confirmBooking: { en: "Confirm booking", de: "Buchung bestätigen", fr: "Confirmer" },
  bookingConfirmed: {
    en: "Booking confirmed!",
    de: "Buchung bestätigt!",
    fr: "Réservation confirmée !",
  },
  bookingConfirmedSub: {
    en: "We have sent the details to your email.",
    de: "Wir haben die Details an deine E-Mail gesendet.",
    fr: "Nous avons envoyé les détails par email.",
  },
  backToHome: { en: "Back to home", de: "Zurück zum Start", fr: "Retour à l'accueil" },
  signIn: { en: "Sign in", de: "Anmelden", fr: "Se connecter" },
  createAccount: { en: "Create account", de: "Konto erstellen", fr: "Créer un compte" },
  email: { en: "Email", de: "E-Mail", fr: "Email" },
  password: { en: "Password", de: "Passwort", fr: "Mot de passe" },
  yourName: { en: "Your name", de: "Dein Name", fr: "Votre nom" },
  continueWithEmail: {
    en: "Continue with email",
    de: "Mit E-Mail fortfahren",
    fr: "Continuer avec email",
  },
  skip: { en: "Continue as guest", de: "Als Gast fortfahren", fr: "Continuer en invité" },
  welcomeTitle: {
    en: "What to do in Luxembourg?",
    de: "Was in Luxemburg unternehmen?",
    fr: "Quoi faire au Luxembourg ?",
  },
  welcomeSub: {
    en: "Discover places, events and workshops — matched to who you are.",
    de: "Entdecke Orte, Events und Workshops — abgestimmt auf dich.",
    fr: "Découvrez lieux et événements adaptés à vos envies.",
  },
  noResults: { en: "No results", de: "Keine Ergebnisse", fr: "Aucun résultat" },
  noSaved: {
    en: "Nothing saved yet. Tap the heart to save your favourites.",
    de: "Noch nichts gespeichert. Tippe das Herz, um Favoriten zu speichern.",
    fr: "Rien d'enregistré. Touchez le cœur pour ajouter.",
  },
  loading: { en: "Loading...", de: "Lädt...", fr: "Chargement..." },

  // -----------------------------------------------------------------------
  // Events tab / For-you personalization
  // -----------------------------------------------------------------------
  forYou:            { en: "FOR YOU",           de: "FÜR DICH",             fr: "POUR VOUS" },
  matchedToInterests:{ en: "Matched to your interests",
                       de: "Passend zu deinen Interessen",
                       fr: "Adapté à vos centres d'intérêt" },
  showAll:           { en: "Show all",          de: "Alle anzeigen",        fr: "Tout afficher" },
  turnPersonalizationBackOn: {
                       en: "Turn personalization back on",
                       de: "Personalisierung wieder einschalten",
                       fr: "Réactiver la personnalisation" },
  personalization:   { en: "Personalization",   de: "Personalisierung",     fr: "Personnalisation" },
  wheelchair:        { en: "Wheelchair",        de: "Rollstuhl",            fr: "Fauteuil roulant" },
  sensoryFriendly:   { en: "Sensory friendly",  de: "Reizarm",              fr: "Adapté aux sens" },
  freeParking:       { en: "Free parking",      de: "Kostenlos parken",     fr: "Parking gratuit" },
  clear:             { en: "Clear",             de: "Löschen",              fr: "Effacer" },
  tryAgain:          { en: "Try again",         de: "Erneut versuchen",     fr: "Réessayer" },
  noEventsYet:       { en: "No events yet",     de: "Noch keine Events",    fr: "Aucun événement pour l'instant" },
  noEventsYetSub: {
    en: "New events are added by the team and partners. Pull to refresh.",
    de: "Neue Events werden vom Team und Partnern hinzugefügt. Zum Aktualisieren nach unten ziehen.",
    fr: "De nouveaux événements sont ajoutés par l'équipe et les partenaires. Tirez pour actualiser.",
  },
  noMatches:         { en: "No matches",        de: "Keine Treffer",        fr: "Aucun résultat" },
  tryRemovingFilter: { en: "Try removing a filter above.",
                       de: "Entferne einen Filter oben.",
                       fr: "Retire un filtre ci-dessus." },
  activity:          { en: "activity",          de: "Aktivität",            fr: "activité" },
  activities:        { en: "activities",        de: "Aktivitäten",          fr: "activités" },
  filtered:          { en: "filtered",          de: "gefiltert",            fr: "filtré" },
  sponsored:         { en: "Sponsored",         de: "Gesponsert",           fr: "Sponsorisé" },
  failedToLoad:      { en: "Failed to load events",
                       de: "Events konnten nicht geladen werden",
                       fr: "Impossible de charger les événements" },

  // -----------------------------------------------------------------------
  // Explore tab
  // -----------------------------------------------------------------------
  browseByCanton:    { en: "Browse by canton",  de: "Nach Kanton stöbern",  fr: "Parcourir par canton" },
  tapCantonToFilter: { en: "Tap a canton to filter activities",
                       de: "Tippe einen Kanton, um zu filtern",
                       fr: "Appuyez sur un canton pour filtrer" },
  anytime:           { en: "Anytime",           de: "Jederzeit",            fr: "À tout moment" },

  // -----------------------------------------------------------------------
  // Profile tab
  // -----------------------------------------------------------------------
  settings:          { en: "Settings",          de: "Einstellungen",        fr: "Paramètres" },
  appearance:        { en: "Appearance",        de: "Erscheinungsbild",     fr: "Apparence" },
  themeLight:        { en: "Light",             de: "Hell",                 fr: "Clair" },
  themeDarkBeta:     { en: "Dark (Beta)",       de: "Dunkel (Beta)",        fr: "Sombre (Beta)" },
  themeSystem:       { en: "System",            de: "System",               fr: "Système" },
  deleteAccount:     { en: "Delete account",    de: "Konto löschen",        fr: "Supprimer le compte" },
  confirmDelete:     { en: "Permanently delete your account and all data?",
                       de: "Konto und alle Daten wirklich unwiderruflich löschen?",
                       fr: "Supprimer définitivement le compte et toutes les données ?" },
  cancel:            { en: "Cancel",            de: "Abbrechen",            fr: "Annuler" },
  delete:            { en: "Delete",            de: "Löschen",              fr: "Supprimer" },

  // -----------------------------------------------------------------------
  // Auth / Login
  // -----------------------------------------------------------------------
  continueWithGoogle:{ en: "Continue with Google",
                       de: "Mit Google fortfahren",
                       fr: "Continuer avec Google" },
  or:                { en: "OR",                de: "ODER",                 fr: "OU" },
  forBusinesses:     { en: "For businesses",    de: "Für Unternehmen",      fr: "Pour les entreprises" },
  comingSoon:        { en: "Coming soon",       de: "Bald verfügbar",       fr: "Bientôt disponible" },
  showing:           { en: "Showing",           de: "Angezeigt:",           fr: "Affichage :" },
  noBookingsYet:     { en: "No bookings yet.",  de: "Noch keine Buchungen.",fr: "Aucune réservation pour l'instant." },
  preferencesTitle:  { en: "Preferences",       de: "Einstellungen",        fr: "Préférences" },
  ageRange:          { en: "Age range",         de: "Altersgruppe",         fr: "Tranche d'âge" },
  favouriteCantons:  { en: "Favourite cantons", de: "Lieblingskantone",     fr: "Cantons favoris" },
  favouriteCategories:{ en: "Favourite categories", de: "Lieblings-Kategorien", fr: "Catégories favorites" },
  notifications:     { en: "Notifications",     de: "Benachrichtigungen",   fr: "Notifications" },
  notifyOnMatch: {
    en: "Notify me when new events match my preferences",
    de: "Benachrichtige mich bei neuen Events, die zu meinen Präferenzen passen",
    fr: "M'avertir des nouveaux événements correspondant à mes préférences",
  },
  notifyBuildHint: {
    en: "Requires the published app build (not Expo Go) and granted notification permission.",
    de: "Erfordert den veröffentlichten App-Build (nicht Expo Go) und die erteilte Benachrichtigungsberechtigung.",
    fr: "Nécessite la version publiée de l'app (pas Expo Go) et l'autorisation des notifications.",
  },
  notSet:            { en: "Not set",           de: "Nicht gesetzt",        fr: "Non défini" },
  bookingsPlural:    { en: "Bookings",          de: "Buchungen",            fr: "Réservations" },
};

export function t(key: keyof typeof STRINGS, lang: Lang): string {
  return STRINGS[key]?.[lang] ?? STRINGS[key]?.en ?? key;
}
