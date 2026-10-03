import { router, usePathname } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Path } from "react-native-svg";
import { useSession } from "../session/SessionProvider";
import { color, font, size, space } from "../theme";

const TITLES: Record<string, string> = {
  "/": "Tessera", "/camera": "Photograph the bottles", "/reading": "Reading labels",
  "/confirm": "One thing to check", "/risks": "What to raise", "/ask": "Ask",
  "/watch": "Watching", "/list": "Saved list",
};

export function Mark({ sizePx = 22, accent = true }: { sizePx?: number; accent?: boolean }) {
  return (
    <Svg width={sizePx} height={sizePx} viewBox="0 0 24 24" fill="none" accessibilityElementsHidden>
      <Path d="M12 2 4 7v10l8 5 8-5V7l-8-5Z" stroke={color.ink} strokeWidth={1.7} strokeLinejoin="round" />
      {accent && <Path d="m8 10 4 2.5L16 10" stroke={color.limeDeep} strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" />}
    </Svg>
  );
}

export function AppBar() {
  const path = usePathname();
  const { reset } = useSession();
  const title = path.startsWith("/citation") ? "Source" : TITLES[path] ?? "Tessera";
  const canBack = path.startsWith("/citation") || path === "/camera" || path === "/list";

  return (
    <View style={s.bar}>
      {canBack ? (
        <Pressable accessibilityRole="button" onPress={() => router.back()} hitSlop={10}>
          <Text style={s.link}>← Back</Text>
        </Pressable>
      ) : <Mark sizePx={16} accent={false} />}
      <Text accessibilityRole="header" style={s.title}>{title}</Text>
      {path !== "/" && (
        <Pressable accessibilityRole="button" onPress={reset} hitSlop={10} style={{ marginLeft: "auto" }}>
          <Text style={s.link}>Start over</Text>
        </Pressable>
      )}
    </View>
  );
}

const TABS = [["/risks", "Risks"], ["/ask", "Ask"], ["/watch", "Watch"]] as const;

export function ResultTabs() {
  const path = usePathname();
  return (
    <View style={s.tabs} accessibilityRole="tablist">
      {TABS.map(([href, label]) => {
        const on = path === href;
        return (
          <Pressable key={href} accessibilityRole="tab" accessibilityState={{ selected: on }}
                     onPress={() => router.replace(href)} style={[s.tab, on && s.tabOn]}>
            <Text style={[s.tabText, on && { color: color.ink }]}>{label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const s = StyleSheet.create({
  bar: { flexDirection: "row", alignItems: "center", gap: space.s2, paddingHorizontal: space.s4,
         minHeight: 49, borderBottomWidth: 1, borderBottomColor: color.border2, backgroundColor: color.paper },
  title: { fontFamily: font.display, fontSize: size.sm, color: color.ink },
  link: { fontFamily: font.bodySemi, fontSize: size.xs, color: color.muted, paddingVertical: 4 },
  tabs: { flexDirection: "row", borderTopWidth: 1, borderTopColor: color.border2, backgroundColor: color.paper },
  tab: { flex: 1, alignItems: "center", paddingTop: 10, paddingBottom: 12, borderTopWidth: 2, borderTopColor: "transparent", marginTop: -1 },
  tabOn: { borderTopColor: color.ink },
  tabText: { fontFamily: font.bodySemi, fontSize: size.xs, color: color.muted },
});
