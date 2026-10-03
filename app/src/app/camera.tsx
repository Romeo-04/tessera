import { CameraView, useCameraPermissions } from "expo-camera";
import { router } from "expo-router";
import { useRef, useState } from "react";
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Button, Note, Screen, T } from "../components/ui";
import type { PhotoInput } from "../lib/api";
import { MAX_PHOTOS, pickPhotos, prepare } from "../media/photos";
import { useSession } from "../session/SessionProvider";
import { color, font, radius, size, space } from "../theme";

/**
 * Multi-shot capture. Several bottles per photo is fine; several photos is
 * fine too - Omni reads them in one call and merges repeats. Every way this
 * can fail (permission denied, no camera, camera error) ends at the photo
 * picker, never at a dead end.
 */
export default function Camera() {
  const { startLive } = useSession();
  const [permission, requestPermission] = useCameraPermissions();
  const [shots, setShots] = useState<PhotoInput[]>([]);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const cam = useRef<CameraView>(null);

  const pickInstead = async () => {
    const photos = await pickPhotos();
    if (photos) {
      router.back();
      await startLive(photos);
    }
  };

  const shoot = async () => {
    if (!cam.current || busy || shots.length >= MAX_PHOTOS) return;
    setBusy(true);
    try {
      const pic = await cam.current.takePictureAsync({ quality: 1, shutterSound: false });
      if (pic) {
        const p = await prepare(pic.uri, pic.width, pic.height, shots.length);
        setShots((s) => (s.length < MAX_PHOTOS ? [...s, p] : s));
      }
    } catch {
      setFailed("The camera could not take that photo.");
    } finally {
      setBusy(false);
    }
  };

  const send = async () => {
    const photos = shots;
    router.back();
    await startLive(photos);
  };

  if (!permission) return <Screen><T>Checking camera access…</T></Screen>;

  if (!permission.granted || failed) {
    return (
      <Screen>
        <T v="h">{failed ? "The camera is not available" : "Camera access"}</T>
        <T>
          {failed
            ? `${failed} You can choose photos you have already taken instead.`
            : "Tessera needs the camera to read the bottle labels. Photos are shrunk on this device, read once, and deleted."}
        </T>
        <View style={{ gap: space.s2 }}>
          {!failed && permission.canAskAgain && <Button label="Allow camera" onPress={requestPermission} />}
          {!failed && !permission.canAskAgain && (
            <Note tone="warn">Camera access was turned off for Tessera. You can turn it back on in Settings, or choose photos instead.</Note>
          )}
          <Button tone="ghost" label="Choose photos instead" onPress={pickInstead} />
        </View>
      </Screen>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: color.ink }}>
      <CameraView ref={cam} style={{ flex: 1 }} facing="back" onCameraReady={() => setReady(true)}
                  onMountError={() => setFailed("This device's camera could not be started.")}
                  accessibilityLabel="Camera preview" />
      <View style={s.hint} pointerEvents="none">
        <Text style={s.hintText}>Labels facing the camera, good light. Several bottles per photo is fine.</Text>
      </View>

      <View style={s.tray}>
        <ScrollView horizontal contentContainerStyle={{ gap: space.s2, paddingHorizontal: space.s4 }}
                    accessibilityLabel={`${shots.length} photo${shots.length === 1 ? "" : "s"} taken`}>
          {shots.map((p, i) => (
            <Pressable key={p.uri} accessibilityRole="button" accessibilityLabel={`Remove photo ${i + 1}`}
                       onPress={() => setShots((s) => s.filter((x) => x.uri !== p.uri))}>
              <Image source={{ uri: p.uri }} style={s.thumb} />
              <Text style={s.remove}>×</Text>
            </Pressable>
          ))}
        </ScrollView>
        <View style={s.controls}>
          <Pressable accessibilityRole="button" onPress={pickInstead} style={s.side}>
            <Text style={s.sideText}>Library</Text>
          </Pressable>
          <Pressable accessibilityRole="button" accessibilityLabel="Take photo"
                     accessibilityState={{ disabled: !ready || busy || shots.length >= MAX_PHOTOS }}
                     disabled={!ready || busy || shots.length >= MAX_PHOTOS} onPress={shoot}
                     style={({ pressed }) => [s.shutter, pressed && { transform: [{ scale: 0.94 }] }, (!ready || busy) && { opacity: 0.5 }]} />
          <Pressable accessibilityRole="button" disabled={shots.length === 0} onPress={send}
                     style={[s.side, s.sendBtn, shots.length === 0 && { opacity: 0.4 }]}>
            <Text style={[s.sideText, { color: color.ink }]}>{shots.length ? `Use ${shots.length}` : "Use"}</Text>
          </Pressable>
        </View>
        <Text style={s.count}>{shots.length}/{MAX_PHOTOS} photos</Text>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  hint: { position: "absolute", top: space.s4, left: space.s4, right: space.s4, backgroundColor: "rgba(10,10,10,0.6)",
          borderRadius: radius.ctrl, padding: space.s2 },
  hintText: { color: "#fff", fontFamily: font.body, fontSize: size.xs, textAlign: "center" },
  tray: { backgroundColor: color.ink, paddingVertical: space.s3, gap: space.s3 },
  thumb: { width: 56, height: 56, borderRadius: 8, borderWidth: 2, borderColor: color.lime },
  remove: { position: "absolute", top: -6, right: -6, width: 20, height: 20, borderRadius: 10, overflow: "hidden",
            backgroundColor: color.paper, color: color.ink, textAlign: "center", fontFamily: font.bodySemi, fontSize: size.sm, lineHeight: 20 },
  controls: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: space.s5 },
  shutter: { width: 68, height: 68, borderRadius: 34, backgroundColor: color.lime, borderWidth: 4, borderColor: "#fff" },
  side: { minWidth: 76, paddingVertical: 10, paddingHorizontal: space.s3, borderRadius: radius.pill, borderWidth: 1, borderColor: "#555", alignItems: "center" },
  sendBtn: { backgroundColor: color.lime, borderColor: color.lime },
  sideText: { color: "#fff", fontFamily: font.bodySemi, fontSize: size.sm },
  count: { color: color.muted2, fontFamily: font.mono, fontSize: size.xs, textAlign: "center" },
});
