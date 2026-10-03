import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Button, Note, Screen, T } from "../components/ui";
import { pickPhotos } from "../media/photos";
import { useSession } from "../session/SessionProvider";
import { color, font, radius, size, space } from "../theme";

const HEIGHTS = [74, 92, 66, 84, 70, 88, 62];

export default function Capture() {
  const { live, notice, startDemo, startLive } = useSession();
  const [picking, setPicking] = useState(false);

  const choose = async () => {
    setPicking(true);
    try {
      const photos = await pickPhotos();
      if (photos) await startLive(photos);
    } finally {
      setPicking(false);
    }
  };

  return (
    <Screen>
      <View style={s.vf} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <View style={s.bottles}>
          {HEIGHTS.map((h, i) => (
            <View key={i} style={{ justifyContent: "flex-end" }}>
              <View style={[s.bottle, { height: h }]}><View style={s.label} /></View>
              <View style={[s.box, { height: h * 0.52 + 4 }]}><Text style={s.boxN}>{i + 1}</Text></View>
            </View>
          ))}
        </View>
        <Text style={s.hint}>One photo can hold every bottle</Text>
      </View>

      <View style={{ marginTop: space.s4, gap: space.s2 }}>
        <T v="h" style={{ marginBottom: 0 }}>Check a medication list</T>
        <T style={{ marginBottom: 4 }}>
          Photograph the bottles with the labels facing the camera. Tessera reads them, asks when
          it is unsure, and shows what the FDA labels document — with the source.
        </T>
        {notice && <Note tone="warn" role="status">{notice}</Note>}

        <Button tone="lime" label="See it with seven real medications" onPress={() => startDemo()} />
        <Button tone="ghost" label="Photograph your own bottles" disabled={!live}
                onPress={() => router.push("/camera")} />
        <Button tone="ghost" label={picking ? "Opening…" : "Choose photos instead"} disabled={!live || picking}
                onPress={choose} />
        <T v="muted" style={{ textAlign: "center" }}>
          {live
            ? "Up to 8 photos. They are shrunk on this device, read once and deleted; only drug codes reach the reasoning service."
            : "Live checking is off on this deployment, so photos cannot be read here. The demo uses the same label corpus."}
        </T>
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  vf: { height: 280, borderRadius: radius.card, backgroundColor: "#2A2A26", alignItems: "center", justifyContent: "center", overflow: "hidden" },
  bottles: { flexDirection: "row", gap: 10, alignItems: "flex-end" },
  bottle: { width: 30, borderTopLeftRadius: 5, borderTopRightRadius: 5, borderRadius: 3, backgroundColor: "#D8D3C6", justifyContent: "center", paddingHorizontal: 3 },
  label: { height: "36%", backgroundColor: "#FBFAF6", borderRadius: 2 },
  box: { position: "absolute", left: -3, right: -3, bottom: -4, borderWidth: 2, borderColor: color.lime, borderRadius: 5 },
  boxN: { position: "absolute", top: -9, left: -2, backgroundColor: color.lime, color: color.ink, fontFamily: font.monoMedium, fontSize: size.xs, paddingHorizontal: 4, borderRadius: 3, overflow: "hidden" },
  hint: { position: "absolute", bottom: space.s3, left: space.s3, right: space.s3, textAlign: "center", color: "#fff",
          fontFamily: font.body, fontSize: size.xs, backgroundColor: "rgba(10,10,10,0.6)", padding: 7, borderRadius: radius.ctrl, overflow: "hidden" },
});
