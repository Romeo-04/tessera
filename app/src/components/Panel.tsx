import { usePathname } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import type { WireEntry } from "../lib/types";
import { useSession } from "../session/SessionProvider";
import { color, font, radius, size, space } from "../theme";

const ALL_TIERS = ["OMNI", "CHEAP", "TOOL", "DEEP"] as const;

type Key = "capture" | "reading" | "confirm" | "results" | "citation" | "ask" | "watch" | "list";

const NARRATION: Record<Key, { title: string; body: string; tiers: string[] }> = {
  capture: {
    title: "One photo, every bottle",
    body: "A caregiver with a shoebox of a parent's medications is never going to type seven "
      + "drug names, spelled correctly, into a form. So the whole input is a photograph.",
    tiers: [],
  },
  reading: {
    title: "One model reads every label",
    body: "Nemotron 3 Nano Omni reads all the photos in a single call and keeps one context "
      + "across them, so two shots of the same bottle are recognised as one drug. Each name is "
      + "then normalised to an RxNorm ingredient code — or deliberately left without one.",
    tiers: ["OMNI"],
  },
  confirm: {
    title: "Abstaining, for real",
    body: "When two different drugs score too close to call, the bottle gets no code at all. A "
      + "code that does not exist cannot cross the gate, so no risk can be built from a "
      + "medication the system has just admitted it cannot name.",
    tiers: ["OMNI"],
  },
  results: {
    title: "A few, not fourteen",
    body: "A deterministic table — derived once from FDA label text and frozen — finds the "
      + "documented pairs. Code ranks them by the label's own severity wording and caps the "
      + "list at five, stating the count. Nemotron Ultra writes each explanation only from "
      + "the cited passage; a separate check drops any sentence the passage does not support.",
    tiers: ["DEEP", "TOOL"],
  },
  citation: {
    title: "Every claim, traceable",
    body: "The passage below the sentence is the evidence, verbatim from the FDA label, with "
      + "a link to the full record on DailyMed. A warning you cannot verify spends the trust "
      + "that makes the verifiable ones worth reading.",
    tiers: ["TOOL"],
  },
  ask: {
    title: "The refusal is code, not a prompt",
    body: "Spoken or typed, a question is screened by a deterministic filter on the device "
      + "before anything else runs. Dose and treatment questions are refused; emergencies are "
      + "sent to emergency care. Everything else is answered only from the cited results.",
    tiers: ["OMNI"],
  },
  watch: {
    title: "Checked, then kept checked",
    body: "A scheduled job searches FDA safety communications for every drug Tessera covers "
      + "and triages them on the cheapest tier. The app downloads them all and keeps only "
      + "its own, so the server never pairs a person with a medication list.",
    tiers: ["CHEAP"],
  },
  list: {
    title: "Saved here, and only here",
    body: "The list is stored on this device and nowhere else — no account, no server copy. "
      + "Re-checking it sends codes only, with no photographs and no perception call.",
    tiers: [],
  },
};

function keyFor(path: string): Key {
  if (path === "/" || path === "/camera") return "capture";
  if (path.startsWith("/citation")) return "citation";
  if (path === "/risks") return "results";
  return (path.slice(1) as Key) in NARRATION ? (path.slice(1) as Key) : "capture";
}

function wireCopy(wire: WireEntry[]): { title: string; body: string } {
  const last = wire[wire.length - 1];
  if (!last) return { title: "Nothing yet", body: "No request has been made. Everything so far is on this device." };
  if (last.boundary === "photos") {
    return {
      title: "The photographs",
      body: "The first boundary, stated honestly: perception runs in the cloud today, so the "
        + "images reach Tessera's API and Nebius for Omni to read. They are deleted after the "
        + "call. On-device Omni is the intended end state and is not built yet.",
    };
  }
  return {
    title: "Codes. Only codes.",
    body: "This is the boundary the privacy gate governs. The reasoning service receives the "
      + "body below and nothing else — the request schema rejects any other field. Names are "
      + "re-joined here, on the device, which had them all along.",
  };
}

export function Panel() {
  const path = usePathname();
  const { wire, mode } = useSession();
  const k = keyFor(path);
  const n = NARRATION[k];
  const w = wireCopy(wire);
  const demoNote = mode === "demo" && k === "results"
    ? " In this demo the ranking and cap are the real code; the explanations were written by hand from each passage, because no model is called."
    : "";

  return (
    <View style={{ gap: space.s4 }} accessibilityLabel="How it works">
      <View style={s.card}>
        <Text style={s.eyebrow}>HOW IT WORKS</Text>
        <Text style={s.h3}>{n.title}</Text>
        <Text style={s.p}>{n.body}{demoNote}</Text>
        <View style={s.tiers}>
          {ALL_TIERS.map((t) => (
            <View key={t} style={[s.tier, n.tiers.includes(t) && s.tierOn]}>
              <Text style={s.tierText}>{t}</Text>
            </View>
          ))}
        </View>
      </View>

      <View style={[s.card, s.dark]} accessibilityLiveRegion="polite">
        <Text style={[s.eyebrow, { color: color.lime }]}>WHAT CROSSED THE NETWORK</Text>
        <Text style={[s.h3, { color: "#fff" }]}>{w.title}</Text>
        <Text style={[s.p, { color: "#C9C9C4" }]}>{w.body}</Text>
        <View style={s.wire}>
          {wire.length === 0 ? <Text style={s.mono}>—</Text> : wire.map((e, i) => (
            <View key={i} style={i > 0 ? s.wireSep : undefined}>
              <Text style={[s.mono, { color: color.wireComment }]}>{e.method} {e.url}{e.sent ? "" : "  (not sent)"}</Text>
              {e.body.split("\n").map((line, j) => (
                <Text key={j} style={[s.mono, line.startsWith("//") && { color: color.wireComment },
                  line.includes('"codes"') && { color: color.lime }]}>{line}</Text>
              ))}
            </View>
          ))}
        </View>
      </View>

      <View style={s.card}>
        <Text style={s.eyebrow}>GROUNDING</Text>
        <Text style={s.h3}>{mode === "demo" ? "This scenario is real" : "Where answers come from"}</Text>
        <Text style={s.p}>
          {mode === "demo"
            ? "Seven medications typical of heart failure with type 2 diabetes. Every interaction "
              + "shown is documented in the FDA label text in Tessera's corpus, ranked and capped "
              + "by the same code the live service runs. Only the plain-language sentences were "
              + "written for the demo, from the quoted passage alone."
            : "FDA Structured Product Labels from DailyMed, normalised with RxNorm. Drugs outside "
              + "the corpus are reported as unchecked — never as safe."}
        </Text>
        {[["Formulary", "358 chronic-care drugs"], ["With label evidence", "285 of 358"],
          ["Label sections", "723"], ["Most risks shown", "5, with the total stated"]].map(([k2, v]) => (
          <View key={k2} style={s.kv}>
            <Text style={s.kvK}>{k2}</Text><Text style={s.kvV}>{v}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  card: { borderWidth: 1, borderColor: color.border, borderRadius: radius.card, padding: space.s5, backgroundColor: color.paper },
  dark: { backgroundColor: color.ink, borderColor: color.ink },
  eyebrow: { fontFamily: font.bodySemi, fontSize: size.xs, letterSpacing: 1.5, color: color.muted2 },
  h3: { fontFamily: font.display, fontSize: size.lg, letterSpacing: -0.7, color: color.ink, marginTop: space.s2, marginBottom: space.s3 },
  p: { fontFamily: font.body, fontSize: size.sm, lineHeight: 22, color: color.ink3 },
  tiers: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: space.s3 },
  tier: { borderWidth: 1, borderColor: color.border, backgroundColor: color.surface, borderRadius: radius.pill, paddingHorizontal: 9, paddingVertical: 4 },
  tierOn: { backgroundColor: color.lime, borderColor: color.ink },
  tierText: { fontFamily: font.monoMedium, fontSize: size.xs, color: color.ink },
  wire: { backgroundColor: color.wire, borderRadius: radius.ctrl, padding: space.s4, marginTop: space.s3 },
  wireSep: { marginTop: space.s4, paddingTop: space.s4, borderTopWidth: 1, borderTopColor: "#33332F", borderStyle: "dashed" },
  mono: { fontFamily: font.mono, fontSize: size.xs, lineHeight: 19, color: color.wireText },
  kv: { flexDirection: "row", gap: space.s4, marginTop: space.s2 },
  kvK: { fontFamily: font.body, fontSize: size.sm, color: color.muted, width: 150 },
  kvV: { fontFamily: font.bodyMedium, fontSize: size.sm, color: color.ink, flex: 1 },
});
