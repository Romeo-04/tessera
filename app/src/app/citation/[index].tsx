import { useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { Note, Screen, Sev, T } from "../../components/ui";
import { citeExcerpt } from "../../lib/cite";
import { pairLabel } from "../../lib/status";
import { demoHighlight } from "../../lib/session";
import { useSession } from "../../session/SessionProvider";
import { color, font, radius, size, space } from "../../theme";

export default function Citation() {
  const { index } = useLocalSearchParams<{ index: string }>();
  const { result, mode } = useSession();
  const [full, setFull] = useState(false);
  const risk = result?.risks[Number(index)];
  if (!risk) return <Screen><T>This risk is no longer in the current result.</T></Screen>;

  const demo = mode === "demo";
  const quote = risk.quote ?? "";
  const ex = citeExcerpt(quote, demo ? demoHighlight(risk.span_id) : null,
    [risk.object_name, risk.subject_name].filter((n): n is string => !!n));
  const shown = ex.pre.length + ex.mark.length + ex.post.length;

  return (
    <Screen>
      <Sev severity={risk.severity} />
      <T v="h" style={{ marginTop: 6 }}>{pairLabel(risk)}</T>
      <T>{risk.mechanism}</T>

      {quote ? (
        <>
          <T v="eyebrow">{risk.subject_name ? `From the ${risk.subject_name.toLowerCase()} label` : "From the FDA label"}</T>
          <View style={s.quote}>
            <Text style={s.quoteText}>
              {full ? quote : (
                <>“{ex.pre}{ex.mark ? <Text style={s.mark}>{ex.mark}</Text> : null}{ex.post}”</>
              )}
            </Text>
          </View>
          {quote.length > shown && (
            <Pressable accessibilityRole="button" onPress={() => setFull((f) => !f)} hitSlop={8}>
              <Text style={s.link}>{full ? "Show the relevant part" : "Show the whole cited passage"}</Text>
            </Pressable>
          )}
        </>
      ) : <Note>The cited passage is on the label page linked below.</Note>}

      <Pressable accessibilityRole="link" onPress={() => Linking.openURL(risk.source_url)}
                 style={({ pressed }) => [s.src, pressed && { backgroundColor: color.surface2 }]}>
        <Text style={s.srcText}>Open the label on DailyMed ↗</Text>
      </Pressable>

      <View style={{ marginTop: space.s4 }}>
        <Note tone="lime">{`What to do: ${risk.action} Tessera never tells you to change a dose.`}</Note>
      </View>
      <T v="muted">
        {demo
          ? "In this demo the sentence was written by hand from the highlighted passage, and the build fails if that passage is not verbatim in the label. Live, a separate model check verifies each sentence against its passage."
          : "This sentence was written only from the passage above, and a separate check confirmed the passage supports it. Sentences that fail that check are removed, not flagged."}
      </T>
    </Screen>
  );
}

const s = StyleSheet.create({
  quote: { backgroundColor: color.surface, borderWidth: 1, borderColor: color.border, borderLeftWidth: 2,
           borderLeftColor: color.muted2, borderTopRightRadius: radius.ctrl, borderBottomRightRadius: radius.ctrl,
           padding: space.s3, marginTop: space.s2, marginBottom: space.s3 },
  quoteText: { fontFamily: font.body, fontSize: size.xs, lineHeight: 19, color: color.ink3 },
  mark: { backgroundColor: color.lime, color: color.ink },
  link: { fontFamily: font.bodySemi, fontSize: size.xs, color: color.muted, marginBottom: space.s3 },
  src: { alignSelf: "flex-start", borderWidth: 1, borderColor: color.ink, borderRadius: radius.pill,
         paddingVertical: 8, paddingHorizontal: space.s3 },
  srcText: { fontFamily: font.bodySemi, fontSize: size.xs, color: color.ink },
});
