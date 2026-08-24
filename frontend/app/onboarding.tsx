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
  BUDGET_OPTIONS,
  CANTON_OPTIONS,
  CHILD_AGE_GROUPS,
  INTEREST_TAGS,
  NEED_TAGS,
  ONBOARDING_COPY,
  PERSONAS,
  type PersonaId,
} from "@/src/data/onboarding";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { pickLang } from "@/src/i18n/pickLang";
import { type Palette, shadowFor } from "@/src/theme";

type Step = "welcome" | "persona" | "ages" | "interests" | "needs" | "cantons" | "budget" | "done";

export default function OnboardingScreen() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const { lang, setUserProfile, markOnboarded } = useApp();

  const [step, setStep] = useState<Step>("welcome");
  const [persona, setPersona] = useState<PersonaId | null>(null);
  const [childAges, setChildAges] = useState<string[]>([]);
  const [interests, setInterests] = useState<string[]>([]);
  const [needs, setNeeds] = useState<string[]>([]);
  const [preferredCantons, setPreferredCantons] = useState<string[]>([]);
  const [budget, setBudget] = useState<string>("");

  const selectedPersona = PERSONAS.find((p) => p.id === persona);

  const stepOrder: Step[] = useMemo(() => {
    if (selectedPersona?.askChildAges) {
      return ["welcome", "persona", "ages", "interests", "needs", "cantons", "budget", "done"];
    }
    return ["welcome", "persona", "interests", "needs", "cantons", "budget", "done"];
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
      preferredCantons,
      budget,
      completedAt: Date.now(),
    });
  }, [persona, childAges, interests, needs, preferredCantons, budget, persistAndExit]);

  const confirmSkip = useCallback(() => {
    Alert.alert(
      pickLang(ONBOARDING_COPY.skipWarnTitle, lang),
      pickLang(ONBOARDING_COPY.skipWarnBody, lang),
      [
        { text: pickLang(ONBOARDING_COPY.cancel, lang), style: "cancel" },
        {
          text: pickLang(ONBOARDING_COPY.skipConfirm, lang),
          style: "destructive",
          onPress: () =>
            persistAndExit({
              persona: "skipped",
              childAgeGroups: [],
              interests: [],
              needs: [],
              preferredCantons: [],
              budget: "",
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
      case "cantons":
        return true;        // multi-select, empty means "all"
      case "budget":
        return !!budget;    // must pick one radio
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
            <Text style={styles.skipTxt}>{pickLang(ONBOARDING_COPY.skip, lang)}</Text>
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
            <Text style={styles.h1}>{pickLang(ONBOARDING_COPY.welcomeTitle, lang)}</Text>
            <Text style={styles.subtitle}>
              {pickLang(ONBOARDING_COPY.welcomeSubtitle, lang)}
            </Text>
          </View>
        )}

        {step === "persona" && (
          <View>
            <Text style={styles.h1}>{pickLang(ONBOARDING_COPY.personaTitle, lang)}</Text>
            <Text style={styles.subtitle}>{pickLang(ONBOARDING_COPY.personaSub, lang)}</Text>
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
                      <Text style={styles.cardTitle}>{pickLang(p.labels, lang)}</Text>
                      <Text style={styles.cardDesc}>{pickLang(p.descriptions, lang)}</Text>
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
            <Text style={styles.h1}>{pickLang(ONBOARDING_COPY.ageTitle, lang)}</Text>
            <Text style={styles.subtitle}>{pickLang(ONBOARDING_COPY.ageSub, lang)}</Text>
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
                      {pickLang(a.labels, lang)}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        )}

        {step === "interests" && (
          <View>
            <Text style={styles.h1}>{pickLang(ONBOARDING_COPY.interestsTitle, lang)}</Text>
            <Text style={styles.subtitle}>
              {pickLang(ONBOARDING_COPY.interestsSub, lang)} · {interests.length}{" "}
                {pickLang(ONBOARDING_COPY.selected, lang)}
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
                      {pickLang(t.labels, lang)}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        )}

        {step === "needs" && (
          <View>
            <Text style={styles.h1}>{pickLang(ONBOARDING_COPY.needsTitle, lang)}</Text>
            <Text style={styles.subtitle}>{pickLang(ONBOARDING_COPY.needsSub, lang)}</Text>
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
                      {pickLang(t.labels, lang)}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        )}

        {step === "cantons" && (
          <View>
            <Text style={styles.h1}>{pickLang(ONBOARDING_COPY.cantonsTitle, lang)}</Text>
            <Text style={styles.subtitle}>
              {pickLang(ONBOARDING_COPY.cantonsSub, lang)} · {preferredCantons.length}{" "}
                {pickLang(ONBOARDING_COPY.selected, lang)}
            </Text>
            <View style={styles.chipsWrap}>
              {CANTON_OPTIONS.map((c) => {
                const active = preferredCantons.includes(c.id);
                return (
                  <TouchableOpacity
                    key={c.id}
                    style={[styles.chip, active && styles.chipActive]}
                    onPress={() =>
                      setPreferredCantons((prev) => toggle(prev, c.id))
                    }
                    testID={`onb-canton-${c.id}`}
                  >
                    <Ionicons
                      name="location-outline"
                      size={14}
                      color={active ? "#fff" : palette.textSecondary}
                      style={{ marginRight: 6 }}
                    />
                    <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>
                      {pickLang(c.labels, lang)}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        )}

        {step === "budget" && (
          <View>
            <Text style={styles.h1}>{pickLang(ONBOARDING_COPY.budgetTitle, lang)}</Text>
            <Text style={styles.subtitle}>{pickLang(ONBOARDING_COPY.budgetSub, lang)}</Text>
            <View style={styles.cardsWrap}>
              {BUDGET_OPTIONS.map((b) => {
                const active = budget === b.id;
                return (
                  <Pressable
                    key={b.id}
                    style={[styles.card, active && styles.cardActive]}
                    onPress={() => setBudget(b.id)}
                    testID={`onb-budget-${b.id}`}
                  >
                    <View style={[styles.cardIcon, active && styles.cardIconActive]}>
                      <Ionicons
                        name={b.icon as keyof typeof Ionicons.glyphMap}
                        size={20}
                        color={active ? "#fff" : palette.primaryDark}
                      />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.cardTitle}>{pickLang(b.labels, lang)}</Text>
                    </View>
                    {active ? (
                      <Ionicons name="checkmark-circle" size={22} color={palette.primary} />
                    ) : null}
                  </Pressable>
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
            <Text style={styles.h1}>{pickLang(ONBOARDING_COPY.doneTitle, lang)}</Text>
            <Text style={styles.subtitle}>{pickLang(ONBOARDING_COPY.doneSub, lang)}</Text>
            <View style={styles.summary}>
              <SummaryRow
                icon={selectedPersona?.icon ?? "person-outline"}
                label={pickLang(selectedPersona?.labels, lang) ?? ""}
              />
              {childAges.length > 0 && (
                <SummaryRow
                  icon="happy-outline"
                  label={childAges.join(" · ")}
                />
              )}
              <SummaryRow
                icon="pricetag-outline"
                label={`${interests.length} ${pickLang(
                    interests.length === 1 ? ONBOARDING_COPY.interestOne : ONBOARDING_COPY.interestMany,
                    lang,
                  )}`}
              />
              {needs.length > 0 && (
                <SummaryRow
                  icon="checkbox-outline"
                  label={`${needs.length} deal-breaker${needs.length === 1 ? "" : "s"}`}
                />
              )}
              {preferredCantons.length > 0 && (
                <SummaryRow
                  icon="location-outline"
                  label={`${preferredCantons.length} canton${preferredCantons.length === 1 ? "" : "s"}`}
                />
              )}
              {budget && (
                <SummaryRow
                  icon={
                    (BUDGET_OPTIONS.find((b) => b.id === budget)?.icon ??
                      "wallet-outline") as string
                  }
                  label={
                    BUDGET_OPTIONS.find((b) => b.id === budget)?.labels[lang] ?? ""
                  }
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
              ? pickLang(ONBOARDING_COPY.finish, lang)
              : pickLang(ONBOARDING_COPY.next, lang)}
          </Text>
          <Ionicons name="arrow-forward" size={18} color="#fff" />
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

function SummaryRow({ icon, label }: { icon: string; label: string }) {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
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

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
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
