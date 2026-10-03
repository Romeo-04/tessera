import { CameraView, useCameraPermissions } from "expo-camera";
import { router } from "expo-router";
import { useRef, useState } from "react";
import { Image, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Button, Note, Screen, T } from "../components/ui";
import type { PhotoInput } from "../lib/api";
import { MAX_PHOTOS, pickPhotos, prepare } from "../media/photos";
import { useSession } from "../session/SessionProvider";
import { color, font, radius, size, space } from "../theme";

/**
 * Multi-shot capture. Several bottles per photo is fine; several photos is
 * fine too - Omni reads them in one call and merges repeats. Every way this
 * can fail (permission denied, no camera, camera error) ends at the photo
 * picker, never at a dead end - and every state has its own Close, because
 * on iOS this full-screen modal covers the app bar.
 */
export default function Camera() {
  const { startLive } = useSession();
  const [permission, requestPermission] = useCameraPermissions();
  const [shots, setShots] = useState<PhotoInput[]>([]);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const cam = useRef<CameraView>(null);

  const close = () => router.back();

  /** From the permission screen: the picker is the whole capture. */
  const pickInstead = async () => {
    const photos = await pickPhotos();
    if (photos) {
      router.back();
      await startLive(photos);
    }
  };

  /** From the live camera: library photos join the tray, not replace it. */
  const addFromLibrary = async () => {
    const photos = await pickPhotos();
    if (photos) setShots((s) => [...s, ...photos].slice(0, MAX_PHOTOS));
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

  if (!permission) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: color.paper }}>
        <Screen><T>Checking camera access…</T><Button tone="ghost" label="Close" onPress={close} /></Screen>
      </SafeAreaView>
    );
  }

  if (!permission.granted || failed) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: color.paper }}>
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
            <>
              <Note tone="warn">Camera access was turned off for Tessera. You can turn it back on in Settings, or choose photos instead.</Note>
              <Button label="Open Settings" onPress={() => void Linking.openSettings()} />
            </>
          )}
          <Button tone="ghost" label="Choose photos instead" onPress={pickInstead} />
          <Button tone="ghost" label="Close" onPress={close} />
        </View>
      </Screen>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: color.ink }} edges={["top", "bottom"]}>
      <CameraView ref={cam} style={{ flex: 1 }} facing="back" onCameraReady={() => setReady(true)}
                  onMountError={() => setFailed("This device's camera could not be started.")}
                  accessibilityLabel="Camera preview" />
      <View style={s.top}>
        <Pressable accessibilityRole="button" onPress={close} hitSlop={10} style={s.close}>
          <Text style={s.closeText}>Close</Text>
        </Pressable>
        <View style={s.hint} pointerEvents="none">
          <Text style={s.hintText}>Labels facing the camera, good light. Several bottles per photo is fine.</Text>
        </View>
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
          <Pressable accessibilityRole="button" accessibilityLabel="Add photos from the library"
                     disabled={shots.length >= MAX_PHOTOS} onPress={addFromLibrary} style={s.side}>
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
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  top: { position: "absolute", top: space.s4, left: space.s4, right: space.s4, flexDirection: "row", gap: space.s2, alignItems: "center" },
  close: { backgroundColor: "rgba(10,10,10,0.7)", borderRadius: radius.pill, paddingVertical: 8, paddingHorizontal: space.s3 },
  closeText: { color: "#fff", fontFamily: font.bodySemi, fontSize: size.sm },
  hint: { flex: 1, backgroundColor: "rgba(10,10,10,0.6)", borderRadius: radius.ctrl, padding: space.s2 },
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
