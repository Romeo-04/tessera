import { router } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { Button, Note, Row, Screen, T } from "../components/ui";
import { useSaved } from "../session/SavedProvider";
import { useSession } from "../session/SessionProvider";
import { space } from "../theme";

export default function SavedListScreen() {
  const { saved, forget } = useSaved();
  const { recheck } = useSession();
  const [confirming, setConfirming] = useState(false);

  if (!saved) {
    return (
      <Screen>
        <T v="h">No saved list</T>
        <T>After a check, you can save the list on this device to re-check it later without photographing the bottles again.</T>
        <Button tone="ghost" label="Back" onPress={() => router.back()} />
      </Screen>
    );
  }

  return (
    <Screen>
      <T v="h">{`${saved.drugs.length} medications`}</T>
      <T v="muted" style={{ marginBottom: space.s4 }}>{`Saved on this device on ${saved.savedAt.slice(0, 10)}. Nowhere else — there is no account and no server copy.`}</T>
      {saved.drugs.map((d) => (
        <Row key={d.rxcui} icon="✓" title={d.display_name ?? d.raw_name} detail={`${d.rxcui} · label read "${d.raw_name}"`} />
      ))}

      {saved.incomplete.length > 0 && (
        <Note tone="warn">{`Not part of this list, so never checked: ${saved.incomplete.join(", ")}. A re-check will say so.`}</Note>
      )}

      <View style={{ gap: space.s2, marginTop: space.s3 }}>
        <Button label="Re-check this list" onPress={() => { router.back(); void recheck(saved.drugs, saved.incomplete); }} />
        <Note>Re-checking sends the codes only — no photographs and no perception call.</Note>
        {confirming ? (
          <>
            <Note tone="warn">This removes the list from this device. It cannot be undone.</Note>
            <Button label="Yes, forget it" onPress={async () => { await forget(); router.back(); }} />
            <Button tone="ghost" label="Keep it" onPress={() => setConfirming(false)} />
          </>
        ) : (
          <Button tone="ghost" label="Forget this list" onPress={() => setConfirming(true)} />
        )}
      </View>
    </Screen>
  );
}
