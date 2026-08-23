import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useState, useMemo } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { CANTONS } from "@/src/data/places";
import { radii, type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { api, ApiEvent, LocalizedString } from "@/src/utils/api";

const CATEGORIES = ["Animals", "Culture", "Playgrounds", "Water", "Nature", "Workshops", "Festivals"];

type Draft = Omit<ApiEvent, "id" | "created_at" | "updated_at" | "created_by">;

const EMPTY_L: LocalizedString = { en: "", de: "", fr: "" };

const EMPTY_DRAFT: Draft = {
  title: { ...EMPTY_L },
  short: { ...EMPTY_L },
  description: { ...EMPTY_L },
  type: "Event",
  canton: "Luxembourg",
  town: "",
  category: [],
  age_min: 0,
  age_max: 99,
  start_date: new Date().toISOString().slice(0, 10),
  end_date: null,
  time: "",
  price_adult: 0,
  price_child: 0,
  price_label: { en: "Free", de: "Gratis", fr: "Gratuit" },
  accessibility: { en: "", de: "", fr: "" },
  weather_fit: { en: "", de: "", fr: "" },
  image: "",
  lat: 49.6116,
  lng: 6.1319,
  bookable: false,
  published: true,
  rating: 4.5,
  featured: false,
  featured_until: null,
  view_count: 0,
  source_id: null,
  source_name: null,
  external_id: null,
  website_url: "",
  accessibility_wheelchair: false,
  sensory_friendly: false,
  free_parking: false,
  sensory_notes: { en: "", de: "", fr: "" },
  parking: { en: "", de: "", fr: "" },
  food_allowed: true,
  food_onsite: { en: "", de: "", fr: "" },
  preparation_tips: { en: "", de: "", fr: "" },
  payment_methods: [],
  opening_hours: { en: "", de: "", fr: "" },
  peak_hours: { en: "", de: "", fr: "" },
  changing_facilities: false,
  restrooms: true,
};

export default function AdminEventEdit() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const isNew = id === "new" || !id;

  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (isNew) return;
    (async () => {
      try {
        // Fetch just this event. This used to download the entire admin list
        // and find the row client-side, which forced the list endpoint to keep
        // returning full documents for every event.
        const found = await api.adminEvent(id);
        const { id: _i, created_at: _c, updated_at: _u, created_by: _b, ...rest } = found;
        void _i;
        void _c;
        void _u;
        void _b;
        setDraft(rest as Draft);
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, [id, isNew]);

  const setField = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));

  const setL = (key: keyof Draft, lang: "en" | "de" | "fr", value: string) =>
    setDraft((d) => ({
      ...d,
      [key]: { ...(d[key] as LocalizedString), [lang]: value } as Draft[keyof Draft],
    }));

  const toggleCategory = (c: string) =>
    setDraft((d) => ({
      ...d,
      category: d.category.includes(c) ? d.category.filter((x) => x !== c) : [...d.category, c],
    }));

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      if (isNew) {
        await api.createEvent(draft);
      } else if (typeof id === "string") {
        await api.updateEvent(id, draft);
      }
      router.replace("/admin/events");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={palette.primary} />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: "#F1F5F9" }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.topbar}>
        <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn} testID="edit-back">
          <Ionicons name="chevron-back" size={18} color={palette.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.h1}>{isNew ? "New event" : "Edit event"}</Text>
        <TouchableOpacity
          onPress={save}
          style={[styles.saveBtn, saving && { opacity: 0.7 }]}
          disabled={saving}
          testID="edit-save"
        >
          {saving ? <ActivityIndicator color="#fff" size="small" /> : (
            <>
              <Ionicons name="checkmark" size={18} color="#fff" />
              <Text style={styles.saveBtnTxt}>Save</Text>
            </>
          )}
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        {err ? <Text style={styles.errTxt}>{err}</Text> : null}

        <Section title="Title (multilingual)">
          <LangField value={draft.title} onChange={(l, v) => setL("title", l, v)} testID="title" />
        </Section>

        <Section title="Short description">
          <LangField
            value={draft.short}
            onChange={(l, v) => setL("short", l, v)}
            multiline
            testID="short"
          />
        </Section>

        <Section title="Full description">
          <LangField
            value={draft.description}
            onChange={(l, v) => setL("description", l, v)}
            multiline
            big
            testID="desc"
          />
        </Section>

        <Section title="Image URL or upload">
          <TextInput
            style={styles.input}
            value={draft.image}
            onChangeText={(v) => setField("image", v)}
            placeholder="https://... or data:image/..."
            placeholderTextColor={palette.textMuted}
            autoCapitalize="none"
            testID="image"
          />
          {Platform.OS === "web" ? (
            <input
              type="file"
              accept="image/*"
              onChange={async (e) => {
                const file = (e.target as HTMLInputElement).files?.[0];
                if (!file) return;
                if (file.size > 2_000_000) {
                  alert("Please choose an image under 2 MB.");
                  return;
                }
                const reader = new FileReader();
                reader.onload = () => {
                  if (typeof reader.result === "string") setField("image", reader.result);
                };
                reader.readAsDataURL(file);
              }}
              style={{ marginTop: 8 }}
            />
          ) : null}
          {draft.image ? (
            <Text style={styles.minilabel}>{draft.image.startsWith("data:") ? "Uploaded image (stored as base64)" : "Linked URL"}</Text>
          ) : null}
        </Section>

        <Section title="Sponsored placement (EUR 49 / month)">
          <TouchableOpacity
            onPress={() => setField("featured", !draft.featured)}
            style={styles.toggleRow}
            testID="toggle-featured"
          >
            <View style={[styles.toggleBox, draft.featured && { borderColor: "#F59E0B", backgroundColor: "#F59E0B" }]}>
              {draft.featured ? <Ionicons name="star" size={14} color="#fff" /> : null}
            </View>
            <Text style={styles.toggleTxt}>
              {draft.featured ? "Featured — promoted on Home & Events" : "Not featured"}
            </Text>
          </TouchableOpacity>
          {draft.featured ? (
            <View style={{ marginTop: 8 }}>
              <Text style={styles.minilabel}>Featured until (YYYY-MM-DD)</Text>
              <TextInput
                style={styles.input}
                value={draft.featured_until ?? ""}
                onChangeText={(v) => setField("featured_until", v || null)}
                placeholder="2026-12-31"
                placeholderTextColor={palette.textMuted}
                testID="featured-until"
              />
            </View>
          ) : null}
        </Section>

        <Section title="Date & time">
          <View style={{ flexDirection: "row", gap: 8 }}>
            <View style={{ flex: 1 }}>
              <Text style={styles.minilabel}>Start (YYYY-MM-DD)</Text>
              <TextInput
                style={styles.input}
                value={draft.start_date}
                onChangeText={(v) => setField("start_date", v)}
                placeholder="2026-06-15"
                placeholderTextColor={palette.textMuted}
                testID="start-date"
              />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.minilabel}>Time</Text>
              <TextInput
                style={styles.input}
                value={draft.time}
                onChangeText={(v) => setField("time", v)}
                placeholder="10:00 - 18:00"
                placeholderTextColor={palette.textMuted}
                testID="time"
              />
            </View>
          </View>
        </Section>

        <Section title="Location">
          <Text style={styles.minilabel}>Town</Text>
          <TextInput
            style={styles.input}
            value={draft.town}
            onChangeText={(v) => setField("town", v)}
            placeholder="Luxembourg City"
            placeholderTextColor={palette.textMuted}
            testID="town"
          />
          <Text style={[styles.minilabel, { marginTop: 10 }]}>Canton</Text>
          <View style={styles.chipsWrap}>
            {CANTONS.map((c) => {
              const active = draft.canton === c;
              return (
                <TouchableOpacity
                  key={c}
                  onPress={() => setField("canton", c)}
                  style={[styles.chip, active && styles.chipActive]}
                  testID={`canton-${c}`}
                >
                  <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>{c}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
          <View style={{ flexDirection: "row", gap: 8, marginTop: 10 }}>
            <View style={{ flex: 1 }}>
              <Text style={styles.minilabel}>Latitude</Text>
              <TextInput
                style={styles.input}
                value={String(draft.lat)}
                onChangeText={(v) => setField("lat", parseFloat(v) || 0)}
                keyboardType="numeric"
                testID="lat"
              />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.minilabel}>Longitude</Text>
              <TextInput
                style={styles.input}
                value={String(draft.lng)}
                onChangeText={(v) => setField("lng", parseFloat(v) || 0)}
                keyboardType="numeric"
                testID="lng"
              />
            </View>
          </View>
        </Section>

        <Section title="Categories">
          <View style={styles.chipsWrap}>
            {CATEGORIES.map((c) => {
              const active = draft.category.includes(c);
              return (
                <TouchableOpacity
                  key={c}
                  onPress={() => toggleCategory(c)}
                  style={[styles.chip, active && styles.chipActive]}
                >
                  <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>{c}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </Section>

        <Section title="Age range">
          <View style={{ flexDirection: "row", gap: 8 }}>
            <View style={{ flex: 1 }}>
              <Text style={styles.minilabel}>Min age</Text>
              <TextInput
                style={styles.input}
                value={String(draft.age_min)}
                onChangeText={(v) => setField("age_min", parseInt(v, 10) || 0)}
                keyboardType="numeric"
              />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.minilabel}>Max age</Text>
              <TextInput
                style={styles.input}
                value={String(draft.age_max)}
                onChangeText={(v) => setField("age_max", parseInt(v, 10) || 99)}
                keyboardType="numeric"
              />
            </View>
          </View>
        </Section>

        <Section title="Price label">
          <LangField value={draft.price_label} onChange={(l, v) => setL("price_label", l, v)} />
        </Section>

        <Section title="Accessibility">
          <LangField value={draft.accessibility} onChange={(l, v) => setL("accessibility", l, v)} />
        </Section>

        <Section title="Weather fit">
          <LangField value={draft.weather_fit} onChange={(l, v) => setL("weather_fit", l, v)} />
        </Section>

        <Section title="Website URL">
          <TextInput
            style={styles.input}
            value={draft.website_url}
            onChangeText={(v) => setField("website_url", v)}
            placeholder="https://..."
            placeholderTextColor={palette.textMuted}
            autoCapitalize="none"
            testID="website-url"
          />
        </Section>

        <Section title="Accessibility & sensory">
          <TouchableOpacity onPress={() => setField("accessibility_wheelchair", !draft.accessibility_wheelchair)} style={styles.toggleRow}>
            <View style={[styles.toggleBox, draft.accessibility_wheelchair && styles.toggleOn]}>
              {draft.accessibility_wheelchair ? <Ionicons name="checkmark" size={14} color="#fff" /> : null}
            </View>
            <Text style={styles.toggleTxt}>Wheelchair accessible</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setField("sensory_friendly", !draft.sensory_friendly)} style={styles.toggleRow}>
            <View style={[styles.toggleBox, draft.sensory_friendly && styles.toggleOn]}>
              {draft.sensory_friendly ? <Ionicons name="checkmark" size={14} color="#fff" /> : null}
            </View>
            <Text style={styles.toggleTxt}>Sensory-friendly (ADHD / Autism)</Text>
          </TouchableOpacity>
          {draft.sensory_friendly ? <LangField value={draft.sensory_notes} onChange={(l, v) => setL("sensory_notes", l, v)} multiline /> : null}
        </Section>

        <Section title="Parking">
          <LangField value={draft.parking} onChange={(l, v) => setL("parking", l, v)} multiline />
        </Section>

        <Section title="Food">
          <TouchableOpacity onPress={() => setField("food_allowed", !draft.food_allowed)} style={styles.toggleRow}>
            <View style={[styles.toggleBox, draft.food_allowed && styles.toggleOn]}>
              {draft.food_allowed ? <Ionicons name="checkmark" size={14} color="#fff" /> : null}
            </View>
            <Text style={styles.toggleTxt}>Outside food / picnic allowed</Text>
          </TouchableOpacity>
          <Text style={styles.minilabel}>On-site food options</Text>
          <LangField value={draft.food_onsite} onChange={(l, v) => setL("food_onsite", l, v)} multiline />
        </Section>

        <Section title="How to prepare (tips)">
          <LangField value={draft.preparation_tips} onChange={(l, v) => setL("preparation_tips", l, v)} multiline big />
        </Section>

        <Section title="Payment methods">
          <View style={styles.chipsWrap}>
            {["cash", "card", "contactless", "mobile pay"].map((m) => {
              const active = draft.payment_methods.includes(m);
              return (
                <TouchableOpacity
                  key={m}
                  onPress={() => setField("payment_methods", active ? draft.payment_methods.filter((x) => x !== m) : [...draft.payment_methods, m])}
                  style={[styles.chip, active && styles.chipActive]}
                >
                  <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>{m}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </Section>

        <Section title="Opening & peak hours">
          <Text style={styles.minilabel}>Opening hours (richer than time field)</Text>
          <LangField value={draft.opening_hours} onChange={(l, v) => setL("opening_hours", l, v)} multiline />
          <Text style={styles.minilabel}>Peak hours / busiest times</Text>
          <LangField value={draft.peak_hours} onChange={(l, v) => setL("peak_hours", l, v)} multiline />
        </Section>

        <Section title="Facilities">
          <TouchableOpacity onPress={() => setField("restrooms", !draft.restrooms)} style={styles.toggleRow}>
            <View style={[styles.toggleBox, draft.restrooms && styles.toggleOn]}>
              {draft.restrooms ? <Ionicons name="checkmark" size={14} color="#fff" /> : null}
            </View>
            <Text style={styles.toggleTxt}>Restrooms available</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setField("changing_facilities", !draft.changing_facilities)} style={styles.toggleRow}>
            <View style={[styles.toggleBox, draft.changing_facilities && styles.toggleOn]}>
              {draft.changing_facilities ? <Ionicons name="checkmark" size={14} color="#fff" /> : null}
            </View>
            <Text style={styles.toggleTxt}>Baby changing facilities</Text>
          </TouchableOpacity>
        </Section>

        <Section title="Publication">
          <TouchableOpacity
            onPress={() => setField("published", !draft.published)}
            style={styles.toggleRow}
            testID="toggle-published"
          >
            <View style={[styles.toggleBox, draft.published && styles.toggleOn]}>
              {draft.published ? <Ionicons name="checkmark" size={14} color="#fff" /> : null}
            </View>
            <Text style={styles.toggleTxt}>
              {draft.published ? "Published — visible to users" : "Draft — hidden from users"}
            </Text>
          </TouchableOpacity>
        </Section>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

function LangField({
  value,
  onChange,
  multiline,
  big,
  testID,
}: {
  value: LocalizedString;
  onChange: (lang: "en" | "de" | "fr", v: string) => void;
  multiline?: boolean;
  big?: boolean;
  testID?: string;
}) {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  return (
    <View style={{ gap: 8 }}>
      {(["en", "de", "fr"] as const).map((l) => (
        <View key={l}>
          <Text style={styles.langBadge}>{l.toUpperCase()}</Text>
          <TextInput
            style={[styles.input, multiline && { minHeight: big ? 100 : 60, textAlignVertical: "top" }]}
            value={value[l]}
            onChangeText={(v) => onChange(l, v)}
            multiline={multiline}
            placeholderTextColor={palette.textMuted}
            testID={`${testID}-${l}`}
          />
        </View>
      ))}
    </View>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#F1F5F9" },
  topbar: {
    paddingHorizontal: 24,
    paddingTop: 28,
    paddingBottom: 16,
    backgroundColor: palette.surface,
    borderBottomWidth: 1,
    borderBottomColor: palette.borderSoft,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  h1: { flex: 1, fontSize: 18, fontWeight: "800", color: palette.textPrimary },
  iconBtn: {
    width: 38,
    height: 38,
    borderRadius: 10,
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    justifyContent: "center",
    alignItems: "center",
  },
  saveBtn: {
    flexDirection: "row",
    gap: 4,
    alignItems: "center",
    backgroundColor: palette.primary,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 12,
    ...shadow.emerald,
  },
  saveBtnTxt: { color: "#fff", fontWeight: "700" },
  scroll: { padding: 24, gap: 18, paddingBottom: 80 },
  errTxt: { color: palette.red },
  section: {
    backgroundColor: palette.surface,
    padding: 16,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    gap: 8,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: palette.textPrimary,
    marginBottom: 4,
  },
  langBadge: {
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 1,
    color: palette.textMuted,
    marginBottom: 4,
  },
  input: {
    fontSize: 14,
    color: palette.textPrimary,
    backgroundColor: palette.surfaceMuted,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  minilabel: { fontSize: 11, fontWeight: "600", color: palette.textMuted, marginBottom: 4 },
  chipsWrap: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    backgroundColor: palette.surface,
  },
  chipActive: { backgroundColor: palette.primary, borderColor: palette.primary },
  chipTxt: { fontSize: 11, fontWeight: "700", color: palette.textSecondary },
  chipTxtActive: { color: "#fff" },
  toggleRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  toggleBox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: palette.border,
    justifyContent: "center",
    alignItems: "center",
  },
  toggleOn: { borderColor: palette.primary, backgroundColor: palette.primary },
  toggleTxt: { fontSize: 13, color: palette.textPrimary, fontWeight: "600" },
});
