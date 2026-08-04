import { Stack, useRouter, useSegments } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AppProvider, useApp } from "@/src/contexts/AppContext";
import { useIconFonts } from "@/src/hooks/use-icon-fonts";

// Keep the native splash visible from cold start until icon fonts register.
// Required because @expo/vector-icons' componentDidMount fallback fires
// Font.loadAsync against a broken vendor path if any <Icon> mounts before
// the family is registered — which throws on Android Expo Go.
SplashScreen.preventAutoHideAsync();

/**
 * Redirects a new user to the onboarding wizard on cold start.
 * We wait until AppProvider has hydrated its state from AsyncStorage
 * (`ready === true`) so we don't false-flag returning users as brand-new.
 */
function OnboardingGate() {
  const { ready, hasOnboarded, user, langPicked } = useApp();
  const router = useRouter();
  const segments = useSegments();

  useEffect(() => {
    if (!ready) return;
    const currentTop = segments[0] ?? "";
    // Step 1 — pick a language before anything else. Skips itself so we
    // don't loop, and skips deep-linked routes if the user is already inside
    // the tabs (which shouldn't happen on a truly fresh install).
    if (!langPicked && currentTop !== "pick-language") {
      router.replace("/pick-language");
      return;
    }
    // Step 2 — once authenticated, push new users into the onboarding wizard.
    const isAuthed = !!user;
    if (
      isAuthed &&
      !hasOnboarded &&
      currentTop !== "onboarding" &&
      currentTop !== "login" &&
      currentTop !== "pick-language"
    ) {
      router.replace("/onboarding");
    }
  }, [ready, hasOnboarded, user, langPicked, segments, router]);

  return null;
}

export default function RootLayout() {
  const [loaded, error] = useIconFonts();

  useEffect(() => {
    if (loaded || error) {
      SplashScreen.hideAsync();
    }
  }, [loaded, error]);

  // If the CDN is unreachable we fall through on error rather than wedging
  // the app — icons will tofu, but the app still boots.
  if (!loaded && !error) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <AppProvider>
          <StatusBar style="dark" />
          <OnboardingGate />
          <Stack
            screenOptions={{
              headerShown: false,
              animation: "slide_from_right",
              contentStyle: { backgroundColor: "#F7F8FA" },
            }}
          />
        </AppProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
