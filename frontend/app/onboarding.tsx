import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useApp, type UserProfile } from "@/src/contexts/AppContext";
import {
  CHILD_AGE_GROUPS,
  INTEREST_TAGS,
  NEED_TAGS,
  ONBOARDING_COPY,
  PERSONAS,
  type PersonaId,
} from "@/src/data/onboarding";

const palette = {
  primary: "#059669",
  primaryDark: "#065F46",
  primaryLight: "#D1FAE5",
  background: "#F7F8FA",
  surface: "#FFFFFF",
  surfaceMuted: "#F3F4F6",
  border: "#E5E7EB",
  textPrimary: "#111827",
  textSecondary: "#4B5563",
  textMuted: "#9CA3AF",
  accent: "#10B981",
};

type Step = "welcome" | "persona" | "ages" | "interests" | "needs" | "done";

export default function OnboardingScreen() {
  const router = useRouter();
  const { lang, setUserProfile, markOnboarded } = useApp();

  const [step, setStep] = useState<Step>("welcome");
  const [persona, setPersona] = useState<PersonaId | null>(null);
  const [childAges, setChildAges] = useState<string[]>([]);
  const [interests, setInterests] = useState<string[]>([]);
  const [needs, setNeeds] = useState<string[]>([]);

  const selectedPersona = PERSONAS.find((p) => p.id === persona);

  // ---------------------------------------------------------------------------
  // Navigation helpers
  // ---------------------------------------------------------------------------
  const stepOrder: Step[] = useMemo(() => {
    if (selectedPersona?.askChildAges) {
      return ["welcome", "persona", "ages", "interests", "needs", "done"];
    }
    return ["welcome", "persona", "interests", "needs", "done"];
  }, [selectedPersona]);

  const currentStepIdx = stepOrder.indexOf(step);

  const goNext = useCallback(() => {
    const next = stepOrder[currentStepIdx + 1];
    if (next) setStep(next);
  }, [stepOrder, currentStepIdx]);

  const goBack = useCallback(() => {
    const prev = stepOrder[currentStepIdx - 1];
    if (prev) setStep(prev);
  }, [stepOrder, currentStepIdx]);

  const persistAndExit = useCallback(
    (profile: UserProfile) => {
      setUserProfile(profile);
      markOnboarded();
      router.replace("/");
    },
    [setUserProfile, markOnboarded, router],
  );

  const finish = useCallback(() => {
    if (!persona) return;
    persistAndExit({
      persona,
      childAgeGroups: childAges,
      interests,
      needs,
      completedAt: Date.now(),
    });
  }, [persona, childAges, interests, needs, persistAndExit]);

  const confirmSkip = useCallback(() => {
    Alert.alert(
      ONBOARDING_COPY.skipWarnTitle[lang],
      ONBOARDING_COPY.skipWarnBody[lang],
      [
        { text: ONBOARDING_COPY.cancel[lang], style: "cancel" },
        {
          text: ONBOARDING_COPY.skipConfirm[lang],
          style: "destructive",
          onPress: () =>
            persistAndExit({
              persona: "skipped",
              childAgeGroups: [],
              interests: [],
              needs: [],
              completedAt: null,
            }),
        },
      ],
    );
  }, [lang, persistAndExit]);

  // Prefill interests when persona changes (nice UX).
  const onPickPersona = useCallback((id: PersonaId) => {
    setPersona(id);
    const preset = PERSONAS.find((p) => p.id === id);
    setInterests(preset?.defaultInterests ?? []);
    // clear ages if not a family
    if (!preset?.askChildAges) setChildAges([]);
  }, []);

  const toggle = (arr: string[], id: string): string[] =>
    arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id];

  // ---------------------------------------------------------------------------
  // Guards
  // ---------------------------------------------------------------------------
  const canProceed = (() => {
    switch (step) {
      case "welcome":
        return true;
      case "persona":
        return !!persona;
      case "ages":
        return childAges.length > 0;
      case "interests":
        return interests.length >= 1;
      case "needs":
        return true;
      case "done":
        return true;
      default:
        return true;
    }
  })();

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      {/* Top bar */}
      <View style={styles.topBar}>
        {step !== "welcome" && step !== "done" ? (
          <TouchableOpacity onPress={goBack} hitSlop={12} testID="onb-back">
            <Ionicons name="chevron-back" size={22} color={palette.textPrimary} />
          </TouchableOpacity>
        ) : (
          <View style={{ width: 22 }} />
        )}

        {/* Progress dots */}
        {step !== "welcome" && step !== "done" ? (
          <View style={styles.dots}>
            {stepOrder.slice(1, -1).map((s, i) => (
              <View
                key={s}
                style={[
                  styles.dot,
                  i <= currentStepIdx - 1 && styles.dotActive,
                ]}
              />
            ))}
          </View>
        ) : (
          <View />
        )}

        {step !== "done" ? (
          <TouchableOpacity onPress={confirmSkip} hitSlop={12} testID="onb-skip">
            <Text style={styles.skipTxt}>{ONBOARDING_COPY.skip[lang]}</Text>
          </TouchableOpacity>
        ) : (
          <View style={{ width: 22 }} />
        )}
      </View>

      {/* Content */}
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {step === "welcome" && (
          <View style={styles.welcome}>
            <View style={styles.heroIcon}>
              <Ionicons name="compass" size={54} color={palette.primaryDark} />
            </View>
            <Text style={styles.h1}>{ONBOARDING_COPY.welcomeTitle[lang]}</Text>
            <Text style={styles.subtitle}>
              {ONBOARDING_COPY.welcomeSubtitle[lang]}
            </Text>
          </View>
        )}

        {step === "persona" && (
          <View>
            <Text style={styles.h1}>{ONBOARDING_COPY.personaTitle[lang]}</Text>
            <Text style={styles.subtitle}>{ONBOARDING_COPY.personaSub[lang]}</Text>
            <View style={styles.cardsWrap}>
              {PERSONAS.map((p) => {
                const active = persona === p.id;
                return (
                  <Pressable
                    key={p.id}
                    style={[styles.card, active && styles.cardActive]}
                    onPress={() => onPickPersona(p.id)}
                    testID={`onb-persona-${p.id}`}
                  >
                    <View style={[styles.cardIcon, active && styles.cardIconActive]}>
                      <Ionicons
                        name={p.icon as keyof typeof Ionicons.glyphMap}
                        size={22}
                        color={active ? "#fff" : palette.primaryDark}
                      />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.cardTitle}>{p.labels[lang]}</Text>
                      <Text style={styles.cardDesc}>{p.descriptions[lang]}</Text>
                    </View>
                    {active ? (
                      <Ionicons
                        name="checkmark-circle"
                        size={22}
                        color={palette.primary}
                      />
                    ) : null}
                  </Pressable>
                );
              })}
            </View>
          </View>
        )}

        {step === "ages" && (
          <View>
            <Text style={styles.h1}>{ONBOARDING_COPY.ageTitle[lang]}</Text>
            <Text style={styles.subtitle}>{ONBOARDING_COPY.ageSub[lang]}</Text>
            <View style={styles.chipsWrap}>
              {CHILD_AGE_GROUPS.map((a) => {
                const active = childAges.includes(a.id);
                return (
                  <TouchableOpacity
                    key={a.id}
                    style={[styles.chip, active && styles.chipActive]}
                    onPress={() => setChildAges((prev) => toggle(prev, a.id))}
                    testID={`onb-age-${a.id}`}
                  >
                    <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>
                      {a.labels[lang]}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        )}

        {step === "interests" && (
          <View>
            <Text style={styles.h1}>{ONBOARDING_COPY.interestsTitle[lang]}</Text>
            <Text style={styles.subtitle}>
              {ONBOARDING_COPY.interestsSub[lang]} · {interests.length} selected
            </Text>
            <View style={styles.chipsWrap}>
              {INTEREST_TAGS.map((t) => {
                const active = interests.includes(t.id);
                return (
                  <TouchableOpacity
                    key={t.id}
                    style={[styles.chip, active && styles.chipActive]}
                    onPress={() => setInterests((prev) => toggle(prev, t.id))}
                    testID={`onb-int-${t.id}`}
                  >
                    <Ionicons
                      name={t.icon as keyof typeof Ionicons.glyphMap}
                      size={14}
                      color={active ? "#fff" : palette.textSecondary}
                      style={{ marginRight: 6 }}
                    />
                    <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>
                      {t.labels[lang]}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        )}

        {step === "needs" && (
          <View>
            <Text style={styles.h1}>{ONBOARDING_COPY.needsTitle[lang]}</Text>
            <Text style={styles.subtitle}>{ONBOARDING_COPY.needsSub[lang]}</Text>
            <View style={styles.chipsWrap}>
              {NEED_TAGS.map((t) => {
                const active = needs.includes(t.id);
                return (
                  <TouchableOpacity
                    key={t.id}
                    style={[styles.chip, active && styles.chipActive]}
                    onPress={() => setNeeds((prev) => toggle(prev, t.id))}
                    testID={`onb-need-${t.id}`}
                  >
                    <Ionicons
                      name={t.icon as keyof typeof Ionicons.glyphMap}
                      size={14}
                      color={active ? "#fff" : palette.textSecondary}
                      style={{ marginRight: 6 }}
                    />
                    <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>
                      {t.labels[lang]}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        )}

        {step === "done" && (
          <View style={styles.welcome}>
            <View style={styles.heroIcon}>
              <Ionicons name="sparkles" size={54} color={palette.primaryDark} />
            </View>
            <Text style={styles.h1}>{ONBOARDING_COPY.doneTitle[lang]}</Text>
            <Text style={styles.subtitle}>{ONBOARDING_COPY.doneSub[lang]}</Text>
            <View style={styles.summary}>
              <SummaryRow
                icon={selectedPersona?.icon ?? "person-outline"}
                label={selectedPersona?.labels[lang] ?? ""}
              />
              {childAges.length > 0 && (
                <SummaryRow
                  icon="happy-outline"
                  label={childAges.join(" · ")}
                />
              )}
              <SummaryRow
                icon="pricetag-outline"
                label={`${interests.length} interest${interests.length === 1 ? "" : "s"}`}
              />
              {needs.length > 0 && (
                <SummaryRow
                  icon="checkbox-outline"
                  label={`${needs.length} deal-breaker${needs.length === 1 ? "" : "s"}`}
                />
              )}
            </View>
          </View>
        )}
      </ScrollView>

      {/* Bottom CTA */}
      <View style={styles.footer}>
        <TouchableOpacity
          disabled={!canProceed}
          onPress={step === "done" ? finish : goNext}
          style={[styles.cta, !canProceed && styles.ctaDisabled]}
          testID="onb-cta"
        >
          <Text style={styles.ctaTxt}>
            {step === "done"
              ? ONBOARDING_COPY.finish[lang]
              : ONBOARDING_COPY.next[lang]}
          </Text>
          <Ionicons name="arrow-forward" size={18} color="#fff" />
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

function SummaryRow({ icon, label }: { icon: string; label: string }) {
  return (
    <View style={styles.summaryRow}>
      <View style={styles.summaryIcon}>
        <Ionicons
          name={icon as keyof typeof Ionicons.glyphMap}
          size={16}
          color={palette.primaryDark}
        />
      </View>
      <Text style={styles.summaryLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: palette.background },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingVertical: 8,
    minHeight: 44,
  },
  skipTxt: { fontSize: 14, fontWeight: "600", color: palette.textSecondary },
  dots: { flexDirection: "row", gap: 6 },
  dot: {
    width: 20,
    height: 4,
    borderRadius: 2,
    backgroundColor: palette.border,
  },
  dotActive: { backgroundColor: palette.primary, width: 24 },
  content: {
    paddingHorizontal: 20,
    paddingTop: 24,
    paddingBottom: 24,
  },
  welcome: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 24,
  },
  heroIcon: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: palette.primaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 24,
  },
  h1: {
    fontSize: 26,
    fontWeight: "800",
    color: palette.textPrimary,
    marginBottom: 8,
    letterSpacing: -0.4,
    textAlign: "left",
  },
  subtitle: {
    fontSize: 15,
    color: palette.textSecondary,
    lineHeight: 22,
    marginBottom: 20,
  },
  cardsWrap: { gap: 10, marginTop: 4 },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 14,
    borderRadius: 16,
    backgroundColor: palette.surface,
    borderWidth: 1.5,
    borderColor: palette.border,
  },
  cardActive: {
    borderColor: palette.primary,
    backgroundColor: "#F0FDF4",
  },
  cardIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: palette.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  cardIconActive: { backgroundColor: palette.primary },
  cardTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: palette.textPrimary,
    marginBottom: 2,
  },
  cardDesc: {
    fontSize: 12,
    color: palette.textSecondary,
    lineHeight: 16,
  },
  chipsWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: palette.surface,
    borderWidth: 1.5,
    borderColor: palette.border,
  },
  chipActive: {
    backgroundColor: palette.primary,
    borderColor: palette.primary,
  },
  chipTxt: { fontSize: 13, fontWeight: "600", color: palette.textSecondary },
  chipTxtActive: { color: "#fff" },
  footer: {
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 12,
  },
  cta: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    height: 52,
    borderRadius: 14,
    backgroundColor: palette.primary,
  },
  ctaDisabled: { backgroundColor: "#9CA3AF" },
  ctaTxt: { color: "#fff", fontSize: 16, fontWeight: "700" },
  summary: {
    marginTop: 24,
    width: "100%",
    padding: 16,
    backgroundColor: palette.surface,
    borderRadius: 16,
    gap: 12,
    borderWidth: 1,
    borderColor: palette.border,
  },
  summaryRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  summaryIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: palette.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  summaryLabel: {
    fontSize: 14,
    color: palette.textPrimary,
    fontWeight: "600",
    flex: 1,
  },
});
