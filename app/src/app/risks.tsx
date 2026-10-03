import { Redirect, router } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { ResultTabs } from "../components/chrome";
import { Button, Note, Screen, Sev, T } from "../components/ui";
import { pairLabel, statusCopy } from "../lib/status";
import { sameList, useSaved } from "../session/SavedProvider";
import { useSession } from "../session/SessionProvider";
import { color, font, radius, size, space } from "../theme";

export default function Risks() {
  const { result, notice, checked } = useSession();
  const { saved, save } = useSaved();
  const isSaved = !!saved && sameList(saved.drugs, checked);
  const canSave = checked.some((d) => d.rxcui);
  const [saveError, setSaveError] = useState<string | null>(null);
  if (!result) return <Redirect href="/" />;

  const onSave = async () => {
    setSaveError(null);
    try {
      // What was left out or outside scope travels with the list, so a later
      // re-check is still reported as incomplete.
      await save(checked, result.excluded_drugs);
    } catch {
      setSaveError("This device would not store the list (storage may be full or private browsing may be on). Nothing was saved.");
    }
  };

  const { title, body } = statusCopy(result.status, result.risks.length);
  const unchecked = result.unchecked_drugs.length;

  return (
    <Screen footer={<ResultTabs />}>
      <T v="h">{title}</T>
      <T style={{ marginBottom: space.s3 }}>{body}</T>
      {notice && <Note tone="warn" role="status">{notice}</Note>}
      {result.notes.map((n, i) => <Note key={i} tone={result.status === "ok" ? "plain" : "warn"}>{n}</Note>)}

      <View style={{ marginTop: space.s3 }} accessibilityRole="list">
        {result.risks.map((r, i) => (
          <Pressable key={r.span_id + i} accessibilityRole="button"
                     accessibilityLabel={`${r.severity}: ${pairLabel(r)}. ${r.mechanism} Opens the source.`}
                     onPress={() => router.push({ pathname: "/citation/[index]", params: { index: String(i) } })}
                     style={({ pressed }) => [s.risk, pressed && s.pressed]}>
            <Sev severity={r.severity} />
            <Text style={s.pair}>{pairLabel(r)}</Text>
            <T v="mech">{r.mechanism}</T>
            <Text style={s.cite}>↗ FDA label · read the source</Text>
          </Pressable>
        ))}
      </View>

      {unchecked > 0 && (
        <Note>{`${unchecked} medication${unchecked === 1 ? " is" : "s are"} recognised but Tessera holds no label evidence for ${unchecked === 1 ? "it" : "them"}, so ${unchecked === 1 ? "it was" : "they were"} not checked.`}</Note>
      )}
      {canSave && (
        <View style={{ marginBottom: space.s3 }}>
          {isSaved
            ? <Note>Saved on this device. Re-check it from the start screen any time.</Note>
            : <Button tone="ghost" label={saved ? "Replace the saved list with this one" : "Save this list on this device"}
                      onPress={() => void onSave()} />}
          {saveError && <Note tone="warn" role="alert">{saveError}</Note>}
        </View>
      )}
      <Note tone="lime">
        Tessera shows what FDA labels document and cites them. It is not medical advice and never
        recommends a dose change — take this list to a pharmacist.
      </Note>
    </Screen>
  );
}

const s = StyleSheet.create({
  risk: { borderWidth: 1, borderColor: color.border, borderRadius: radius.card, padding: space.s3,
          marginBottom: space.s3, backgroundColor: color.paper, gap: 6 },
  pressed: { borderColor: color.ink },
  pair: { fontFamily: font.display, fontSize: size.sm, color: color.ink },
  cite: { fontFamily: font.bodyMedium, fontSize: size.xs, color: color.muted, marginTop: 2 },
});
