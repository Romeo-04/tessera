import { BricolageGrotesque_700Bold, BricolageGrotesque_800ExtraBold } from "@expo-google-fonts/bricolage-grotesque";
import { IBMPlexMono_400Regular, IBMPlexMono_500Medium } from "@expo-google-fonts/ibm-plex-mono";
import {
  IBMPlexSans_400Regular, IBMPlexSans_500Medium, IBMPlexSans_600SemiBold,
} from "@expo-google-fonts/ibm-plex-sans";
import { useFonts } from "expo-font";
import { router, Stack, usePathname } from "expo-router";
import { useEffect } from "react";
import { StatusBar } from "expo-status-bar";
import type { ReactNode } from "react";
import { Alert, BackHandler, Platform, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { AppBar, Mark } from "../components/chrome";
import { Panel } from "../components/Panel";
import { SavedProvider } from "../session/SavedProvider";
import { SessionProvider, useSession } from "../session/SessionProvider";
import { color, font, radius, size, space, WIDE } from "../theme";

/**
 * Android's hardware back, step by step through a check:
 *   Ask / Watch -> Risks (the tabs are one result, not a history)
 *   Confirm     -> Reading (an ordinary step back)
 *   Reading     -> start over (nothing to keep yet)
 *   Risks       -> start over, but a live result is a paid check, so ask first
 * Everything else (citation, camera, saved list) is the stack's normal pop.
 */
function useFlowBack() {
  const path = usePathname();
  const { reset, mode } = useSession();
  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (path === "/ask" || path === "/watch") {
        router.replace("/risks");
        return true;
      }
      if (path === "/reading") {
        reset();
        return true;
      }
      if (path === "/risks") {
        if (mode === "demo") {
          reset();
        } else {
          Alert.alert("Start over?", "This result will be cleared. Checking again means photographing the bottles again — or save the list first.", [
            { text: "Keep it", style: "cancel" },
            { text: "Start over", style: "destructive", onPress: reset },
          ]);
        }
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [path, reset, mode]);
}

function Flow() {
  useFlowBack();
  return (
    <View style={{ flex: 1, backgroundColor: color.paper }}>
      <AppBar />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: color.paper } }}>
        <Stack.Screen name="reading" options={{ gestureEnabled: false }} />
        <Stack.Screen name="confirm" />
        <Stack.Screen name="risks" options={{ animation: "none", gestureEnabled: false }} />
        <Stack.Screen name="ask" options={{ animation: "none", gestureEnabled: false }} />
        <Stack.Screen name="watch" options={{ animation: "none", gestureEnabled: false }} />
        <Stack.Screen name="camera" options={{ presentation: "fullScreenModal" }} />
      </Stack>
    </View>
  );
}

function ModeChip() {
  const { mode } = useSession();
  return (
    <View style={[s.chip, mode === "demo" && s.chipLime]}>
      <View style={[s.dot, mode === "live" && { backgroundColor: color.ok }]} />
      <Text style={s.chipText}>{mode === "demo" ? "Seeded demo" : "Live"}</Text>
    </View>
  );
}

/** Wide web: the app in a phone frame beside the explanation panel - the judge's view. */
function WideShell({ children }: { children: ReactNode }) {
  return (
    <ScrollView style={{ backgroundColor: color.page }} contentContainerStyle={{ padding: space.s5 }}>
      <View style={s.sheet}>
        <View style={s.top}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: space.s2 }}>
            <Mark /><Text style={s.brand}>Tessera</Text>
          </View>
          <ModeChip />
          <View style={s.chip}><Text style={s.chipText}>Real FDA label text</Text></View>
          <View style={s.chip}><Text style={s.chipText}>iOS · Android · Web</Text></View>
          <Text style={s.tag}>
            Photograph the bottles. Get a short, ranked list of documented interaction risks —
            each linked to the FDA label text it came from.
          </Text>
        </View>
        <View style={s.stage}>
          <View style={s.phone}>
            <View style={s.screen}>{children}</View>
          </View>
          <View style={{ flex: 1, minWidth: 0 }}><Panel /></View>
        </View>
        <View style={s.foot}>
          <Text style={s.footText}>Tessera · Personal AI track · Nebius × NVIDIA · Apache-2.0</Text>
          <Text style={s.footText}>Not medical advice, and not a clinical device. It never recommends a dose change.</Text>
        </View>
      </View>
    </ScrollView>
  );
}

function Shell() {
  const { width } = useWindowDimensions();
  if (Platform.OS === "web" && width >= WIDE) return <WideShell><Flow /></WideShell>;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: color.paper }} edges={["top", "bottom"]}>
      <Flow />
    </SafeAreaView>
  );
}

export default function RootLayout() {
  const [loaded, fontError] = useFonts({
    BricolageGrotesque_700Bold, BricolageGrotesque_800ExtraBold,
    IBMPlexSans_400Regular, IBMPlexSans_500Medium, IBMPlexSans_600SemiBold,
    IBMPlexMono_400Regular, IBMPlexMono_500Medium,
  });
  // A font that fails to load falls back to the system font; it must never
  // leave the app on a blank screen.
  if (!loaded && !fontError) return null;
  return (
    <SafeAreaProvider>
      <SavedProvider>
        <SessionProvider>
          <StatusBar style="dark" />
          <Shell />
        </SessionProvider>
      </SavedProvider>
    </SafeAreaProvider>
  );
}

const s = StyleSheet.create({
  sheet: { maxWidth: 1340, width: "100%", alignSelf: "center", backgroundColor: color.paper,
           borderRadius: radius.panel, overflow: "hidden" },
  top: { flexDirection: "row", alignItems: "center", flexWrap: "wrap", gap: space.s3,
         paddingVertical: space.s5, paddingHorizontal: space.s7, borderBottomWidth: 1, borderBottomColor: color.border2 },
  brand: { fontFamily: font.displayHeavy, fontSize: size.md, letterSpacing: -0.7, color: color.ink },
  tag: { marginLeft: "auto", maxWidth: 360, textAlign: "right", fontFamily: font.body, fontSize: size.xs, lineHeight: 17, color: color.muted },
  chip: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 12, paddingVertical: 5,
          borderRadius: radius.pill, borderWidth: 1, borderColor: color.border, backgroundColor: color.paper },
  chipLime: { backgroundColor: color.lime, borderColor: color.ink },
  chipText: { fontFamily: font.bodySemi, fontSize: size.xs, color: color.ink },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: color.muted2 },
  stage: { flexDirection: "row", gap: space.s7, padding: space.s7, alignItems: "flex-start" },
  phone: { width: 400, backgroundColor: color.ink, borderRadius: 44, padding: 12 },
  screen: { height: 760, backgroundColor: color.paper, borderRadius: 34, overflow: "hidden" },
  foot: { backgroundColor: color.ink, paddingVertical: space.s6, paddingHorizontal: space.s7,
          flexDirection: "row", justifyContent: "space-between", flexWrap: "wrap", gap: space.s4 },
  footText: { fontFamily: font.body, fontSize: size.xs, color: "#BFBFBA" },
});
