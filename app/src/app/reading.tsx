import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";
import { Button, Note, Row, Screen, T } from "../components/ui";
import { useSession } from "../session/SessionProvider";
import { color, space } from "../theme";

export default function Reading() {
  const { mode, busy, drugs, ambiguities, excluded, notice, result, afterReading } = useSession();
  const unsure = new Set(ambiguities.map((a) => a.raw_name));
  const total = drugs.length + excluded.length;
  // A saved-list re-check passes through here while /api/assess runs.
  const assessing = busy && drugs.length > 0;
  if (!busy && drugs.length === 0 && excluded.length === 0 && !notice) return <Redirect href="/" />;

  return (
    <Screen>
      <T v="h">{busy ? (assessing ? "Checking for interactions…" : "Reading the labels…") : `Read ${total} label${total === 1 ? "" : "s"}`}</T>
      <T v="muted" style={{ marginBottom: space.s4 }}>
        {assessing ? "Codes only, to the reasoning service" : `Nemotron 3 Nano Omni · one call for every photo${mode === "demo" ? " · demo" : ""}`}
      </T>
      {busy && <ActivityIndicator color={color.ink} style={{ marginVertical: space.s5 }} />}

      {!busy && drugs.map((d, i) => {
        const ask = unsure.has(d.raw_name) || d.rxcui === null;
        return (
          <Row key={d.raw_name + i} icon={ask ? "?" : "✓"} tone={ask ? "ask" : "plain"}
               title={d.display_name ?? d.raw_name}
               detail={ask ? "could not tell which — we will ask" : [d.strength, d.form].filter(Boolean).join(" ") || d.raw_name} />
        );
      })}
      {!busy && excluded.map((name) => (
        <Row key={name} icon="–" tone="out" title={name} detail="outside the checked list" />
      ))}

      {notice && mode === "live" && (
        <Note tone="warn" role="alert">{`${notice} Nothing was checked; try again.`}</Note>
      )}
      {notice && mode === "demo" && <Note tone="warn" role="status">{notice}</Note>}

      {!busy && !result && (
        <View style={{ marginTop: space.s3 }}>
          <Button label={ambiguities.length ? "Continue" : "Check for interactions"} onPress={afterReading} />
        </View>
      )}
    </Screen>
  );
}
