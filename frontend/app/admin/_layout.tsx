import { Stack } from "expo-router";

export default function AdminLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: "#F1F5F9" },
      }}
    />
  );
}
