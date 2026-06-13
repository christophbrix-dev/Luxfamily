import { Redirect } from "expo-router";

import { useApp } from "@/src/contexts/AppContext";

export default function Index() {
  const { ready, user } = useApp();
  if (!ready) return null;
  if (!user) return <Redirect href="/login" />;
  return <Redirect href="/(tabs)/home" />;
}
