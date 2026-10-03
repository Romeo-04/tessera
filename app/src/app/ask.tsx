import { Redirect } from "expo-router";
import { useState } from "react";
import { Linking, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { ResultTabs } from "../components/chrome";
import { Screen, T } from "../components/ui";
import { screenQuestion } from "../lib/guardrail";
import { pairLabel } from "../lib/status";
import type { Drug, SessionResult } from "../lib/types";
import { useSession } from "../session/SessionProvider";
import { color, font, radius, size, space } from "../theme";

type Turn = { who: "me" | "app"; kind?: "answer" | "clarify" | "refuse" | "urgent"; text: string; cite?: string };

const SUGGESTED = [
  "Can he take the water pill with the blood pressure one?",
  "Is the blood thinner OK with the cholesterol one?",
  "Should I lower his warfarin dose until we see the doctor?",
];

/** Answers are assembled from already-cited risks. Nothing here writes new text about drugs. */
function respond(q: string, drugs: Drug[], result: SessionResult): Turn[] {
  const r = screenQuestion(q, drugs);
  if (r.kind !== "answer") return [{ who: "app", kind: r.kind, text: r.message }];

  const asked = new Set(r.codes);
  const names = drugs.filter((d) => d.rxcui && asked.has(d.rxcui)).map((d) => d.display_name ?? d.raw_name);
  const hits = result.risks.filter((x) => asked.has(x.subject) && asked.has(x.object));
  if (hits.length === 0) {
    const capped = result.notes.some((n) => n.includes("most severe"));
    return [{
      who: "app", kind: "answer",
      text: `${names.join(", ")}: nothing in the results above documents an interaction between these. `
        + (capped ? "More documented interactions were found than the five shown, so one between these may be among those not shown. " : "")
        + "That is not the same as safe — labels do not cover everything. A pharmacist can check.",
    }];
  }
  return [
    ...hits.map((x): Turn => ({ who: "app", kind: "answer", text: `${pairLabel(x)}: ${x.mechanism}`, cite: x.source_url })),
    { who: "app", kind: "answer", text: "Whether that matters for the person taking them is a question for their pharmacist — bring this list." },
  ];
}

export default function Ask() {
  const { checked, result } = useSession();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  if (!result) return <Redirect href="/" />;

  const ask = (question: string) => {
    const text = question.trim();
    if (!text) return;
    setTurns((t) => [...t, { who: "me", text }, ...respond(text, checked, result)]);
    setQ("");
  };

  const bar = (
    <View>
      <View style={s.bar}>
        <TextInput value={q} onChangeText={setQ} onSubmitEditing={() => ask(q)} placeholder="Type a question"
                   placeholderTextColor={color.muted2} accessibilityLabel="Your question" returnKeyType="send"
                   style={s.input} />
        <Pressable accessibilityRole="button" onPress={() => ask(q)} style={s.send}>
          <Text style={s.sendText}>Ask</Text>
        </Pressable>
      </View>
      <ResultTabs />
    </View>
  );

  return (
    <Screen footer={bar} followEnd>
      <T>
        Ask about two medications on this list. Answers come only from the cited results — and
        some questions Tessera will not answer at all.
      </T>
      {turns.length === 0 && (
        <View style={s.suggest}>
          {SUGGESTED.map((x) => (
            <Pressable key={x} accessibilityRole="button" onPress={() => ask(x)} style={s.chip}>
              <Text style={s.chipText}>{x}</Text>
            </Pressable>
          ))}
        </View>
      )}
      <View accessibilityLiveRegion="polite">
        {turns.map((t, i) => t.who === "me" ? (
          <View key={i} style={[s.bubble, s.me]}><Text style={s.meText}>{t.text}</Text></View>
        ) : t.kind === "refuse" || t.kind === "urgent" ? (
          <View key={i} style={s.refuse} accessibilityRole="alert">
            <Text style={s.refuseT}>{t.kind === "urgent" ? "Get help now" : "Tessera will not answer that"}</Text>
            <T style={{ marginBottom: 0 }}>{t.text}</T>
          </View>
        ) : (
          <View key={i} style={[s.bubble, s.app]}>
            <Text style={s.appText}>{t.text}</Text>
            {t.cite && (
              <Pressable accessibilityRole="link" onPress={() => Linking.openURL(t.cite!)}>
                <Text style={s.cite}>FDA label · source ↗</Text>
              </Pressable>
            )}
          </View>
        ))}
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  suggest: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: space.s3 },
  chip: { borderWidth: 1, borderColor: color.border, borderRadius: radius.pill, paddingVertical: 6, paddingHorizontal: 10 },
  chipText: { fontFamily: font.body, fontSize: size.xs, color: color.ink },
  bubble: { paddingVertical: 10, paddingHorizontal: space.s3, borderRadius: 14, marginBottom: space.s2, maxWidth: "88%" },
  me: { backgroundColor: color.ink, alignSelf: "flex-end", borderBottomRightRadius: 4 },
  meText: { fontFamily: font.body, fontSize: size.sm, lineHeight: 21, color: "#fff" },
  app: { backgroundColor: color.surface2, borderWidth: 1, borderColor: color.border, alignSelf: "flex-start", borderBottomLeftRadius: 4 },
  appText: { fontFamily: font.body, fontSize: size.sm, lineHeight: 21, color: color.ink },
  cite: { fontFamily: font.bodyMedium, fontSize: size.xs, color: color.muted, marginTop: 6, textDecorationLine: "underline" },
  refuse: { borderWidth: 2, borderColor: color.danger, backgroundColor: color.dangerWash, borderRadius: radius.card,
            padding: space.s4, marginBottom: space.s2 },
  refuseT: { fontFamily: font.display, fontSize: size.sm, color: color.danger, marginBottom: 6 },
  bar: { flexDirection: "row", gap: space.s2, paddingVertical: space.s3, paddingHorizontal: space.s4,
         borderTopWidth: 1, borderTopColor: color.border2, backgroundColor: color.paper },
  input: { flex: 1, minWidth: 0, fontFamily: font.body, fontSize: size.sm, color: color.ink, paddingVertical: 10,
           paddingHorizontal: space.s3, borderWidth: 1, borderColor: color.border, borderRadius: radius.pill, backgroundColor: color.surface },
  send: { backgroundColor: color.ink, borderRadius: radius.pill, paddingHorizontal: space.s4, justifyContent: "center" },
  sendText: { fontFamily: font.bodySemi, fontSize: size.sm, color: "#fff" },
});
