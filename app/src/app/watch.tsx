import { Redirect } from "expo-router";
import { useEffect, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { ResultTabs } from "../components/chrome";
import { Note, Row, Screen, T } from "../components/ui";
import { fetchAlerts } from "../lib/api";
import { type AlertsFile, watchView } from "../lib/watch";
import { useSession } from "../session/SessionProvider";
import { color, font, radius, size, space } from "../theme";

export default function Watch() {
  const { checked, mode, result } = useSession();
  const [file, setFile] = useState<AlertsFile | null | "loading">("loading");
  const coded = checked.filter((d) => d.rxcui);
  const codes = coded.map((d) => d.rxcui as string);
  const names = new Map(coded.map((d) => [d.rxcui, d.display_name ?? d.raw_name]));

  useEffect(() => {
    let alive = true;
    fetchAlerts().then((f) => { if (alive) setFile(f); });
    return () => { alive = false; };
  }, []);

  const view = file === "loading" ? null : watchView(file, codes);
  if (!result) return <Redirect href="/" />;

  return (
    <Screen footer={<ResultTabs />}>
      <T>
        A one-time check goes stale: FDA safety communications are published continuously. The
        server watches every drug Tessera covers, and this app picks out the {codes.length} on
        your list — so the server never learns whose list it is.
      </T>

      {file === "loading" && <Note>Checking for FDA safety communications…</Note>}
      {view?.kind === "unreachable" && (
        <Note>{`The watcher runs on Tessera's server, and this ${mode === "demo" ? "demo deployment" : "connection"} cannot reach it, so nothing has been checked. Nothing here is invented to fill the gap.`}</Note>
      )}
      {view?.kind === "never_run" && (
        <Note tone="warn">The watcher has not run on this server yet, so these medications have not been checked for safety communications.</Note>
      )}
      {view?.kind === "ran" && view.unchecked.length > 0 && (
        <Note tone="warn">{`The last watch run (${view.generatedAt.slice(0, 10)}) could not check: ${view.unchecked.map((c) => names.get(c) ?? c).join(", ")}. No news is not good news for these.`}</Note>
      )}
      {view?.kind === "ran" && view.clear && (
        <Note tone="lime">{`No FDA safety communications turned up for these medications in the last watch run (${view.generatedAt.slice(0, 10)}). It is a search of fda.gov, not a guarantee.`}</Note>
      )}
      {view?.kind === "ran" && view.alerts.map((a) => (
        <View key={a.url + a.rxcui} style={s.notif}>
          <T v="eyebrow">{`${names.get(a.rxcui) ?? a.rxcui}${a.published ? ` · ${a.published}` : ""}`}</T>
          <Text style={s.title}>{a.title}</Text>
          <T v="muted">{a.summary}</T>
          <Pressable accessibilityRole="link" onPress={() => Linking.openURL(a.url)} style={s.src}>
            <Text style={s.srcText}>Read it on fda.gov ↗</Text>
          </Pressable>
        </View>
      ))}

      <View style={{ marginTop: space.s4 }}>
        {coded.map((d) => <Row key={d.rxcui} icon="◔" title={d.display_name ?? d.raw_name} detail={d.rxcui ?? ""} />)}
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  notif: { borderWidth: 1, borderColor: color.border, borderRadius: radius.card, padding: space.s3, marginBottom: space.s3, gap: 4 },
  title: { fontFamily: font.bodySemi, fontSize: size.sm, color: color.ink },
  src: { alignSelf: "flex-start", borderWidth: 1, borderColor: color.ink, borderRadius: radius.pill, paddingVertical: 8, paddingHorizontal: space.s3, marginTop: space.s2 },
  srcText: { fontFamily: font.bodySemi, fontSize: size.xs, color: color.ink },
});
