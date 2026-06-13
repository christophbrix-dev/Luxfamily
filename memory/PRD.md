# Luxembourg Family Activities — Mobile App PRD

## Overview
Native Expo mobile app for families in Luxembourg to discover places, events, and workshops for kids. Converted from the user-provided React web prototype, with the requested feature extensions.

## Tech Stack
- Expo SDK 54 + expo-router (file-based)
- React Native (View/Text/TouchableOpacity/ScrollView/Image)
- `@expo/vector-icons` Ionicons (Lucide-equivalents)
- `expo-linear-gradient`, `react-native-webview` (map embed)
- `react-native-safe-area-context`
- Local-only persistence via `@/src/utils/storage` (no backend)

## Architecture
- `/app/_layout.tsx` — Root: SafeAreaProvider + GestureHandlerRootView + AppProvider + Stack
- `/app/index.tsx` — Auth gate (Redirect to login or tabs)
- `/app/login.tsx` — Sign in / Sign up / Guest, with language picker
- `/app/(tabs)/_layout.tsx` — Custom bottom tab bar
- `/app/(tabs)/{home,explore,saved,calendar,profile}.tsx`
- `/app/detail/[id].tsx` — Place detail with embedded OpenStreetMap
- `/app/book/[id].tsx` — Multi-step booking flow + confirmation
- `/src/components/{AppCard,Chip,FilterSheet,WeatherWidget,MapPreview,BottomTabBar}.tsx`
- `/src/contexts/AppContext.tsx` — Language, user, saved, bookings (AsyncStorage)
- `/src/data/places.ts` — 8 seeded Luxembourg activities with EN/DE/FR strings
- `/src/i18n/strings.ts` — Translation dictionary (EN/DE/FR)
- `/src/utils/weather.ts` — Open-Meteo API (no key needed)

## Features
- Multilingual UI (EN/DE/FR) — switchable from login + profile
- Real-time Luxembourg weather widget (Open-Meteo)
- 5-tab navigation: Home / Explore / Saved / Calendar / Profile
- Filterable explore feed (age / type / category / date) via bottom sheet
- Save / unsave activities (persisted in AsyncStorage)
- Booking flow with date picker, guest stepper, total computation, confirmation
- Detail screen with embedded OpenStreetMap + "Open in Maps" deep link
- Local-only profile (email/name) stored in AsyncStorage
- Saved bookings show up in Calendar tab "Your booking" chip

## Notes / MOCKED
- Authentication is local-only (no backend). Email/password are stored in AsyncStorage; no real password hashing or remote auth. This matches the user's explicit choice ("static data, no backend").
- Booking is a UI-only flow; no payment integration. Total is calculated and persisted locally.
- Maps use OpenStreetMap embed via WebView (no API key required).
- Weather uses the free Open-Meteo public endpoint (no API key required).

## Next Action Items
- Backend wiring (FastAPI + MongoDB) when the user wants real users / bookings / partner listings
- Real payment integration (Stripe) for the booking confirmation step
- Push notifications for reminders on upcoming bookings (requires deployment + dev build)
