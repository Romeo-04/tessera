import { useRef, type ReactNode } from "react";
import {
  KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View,
  type PressableProps, type StyleProp, type TextStyle, type ViewStyle,
} from "react-native";
import { color, font, radius, severityStyle, size, space } from "../theme";
import type { Severity } from "../lib/types";

type Variant = "h" | "p" | "muted" | "eyebrow" | "pair" | "mech" | "mono";

export function T({ v = "p", style, children, ...rest }:
  { v?: Variant; style?: StyleProp<TextStyle>; children: ReactNode } & React.ComponentProps<typeof Text>) {
  return <Text style={[s[v], style]} {...rest}>{children}</Text>;
}

export function Screen({ children, footer, followEnd }:
  { children: ReactNode; footer?: ReactNode; followEnd?: boolean }) {
  const ref = useRef<ScrollView>(null);
  // A footer holding a text input must ride above the keyboard. iOS needs the
  // padding; Android under edge-to-edge does not resize the window by itself.
  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: color.paper }}
                          behavior={Platform.OS === "ios" ? "padding" : Platform.OS === "android" ? "height" : undefined}>
      <ScrollView ref={ref} contentContainerStyle={{ padding: space.s4, paddingBottom: space.s6 }}
                  keyboardShouldPersistTaps="handled"
                  onContentSizeChange={followEnd ? () => ref.current?.scrollToEnd({ animated: true }) : undefined}>
        {children}
      </ScrollView>
      {footer}
    </KeyboardAvoidingView>
  );
}

type Tone = "ink" | "lime" | "ghost";

export function Button({ label, tone = "ink", disabled, onPress, style, ...rest }:
  { label: string; tone?: Tone; style?: StyleProp<ViewStyle> } & Omit<PressableProps, "style">) {
  return (
    <Pressable
      accessibilityRole="button" accessibilityState={{ disabled: !!disabled }}
      disabled={disabled} onPress={onPress}
      style={({ pressed }) => [s.btn, s[`btn_${tone}`], pressed && s.btnPressed, disabled && s.btnDisabled, style]}
      {...rest}
    >
      <Text style={[s.btnText, tone === "ink" ? { color: "#fff" } : { color: color.ink }]}>{label}</Text>
    </Pressable>
  );
}

export function Note({ tone = "plain", children, role }:
  { tone?: "plain" | "lime" | "warn"; children: ReactNode; role?: "alert" | "status" }) {
  const bg = tone === "lime" ? [color.limeWash, color.limeDeep] : tone === "warn" ? [color.warnWash, color.warnLine] : [color.surface, color.border];
  return (
    <View accessibilityRole={role === "alert" ? "alert" : undefined} accessibilityLiveRegion={role ? "polite" : undefined}
          style={[s.note, { backgroundColor: bg[0], borderColor: bg[1] }]}>
      {typeof children === "string" ? <T v="mech">{children}</T> : children}
    </View>
  );
}

export function Row({ icon, title, detail, tone = "plain", onPress, selected, disabled }:
  { icon: string; title: string; detail?: string; tone?: "plain" | "ask" | "out";
    onPress?: () => void; selected?: boolean; disabled?: boolean }) {
  const body = (
    <>
      <View style={s.rowIc}><Text style={s.rowIcText}>{icon}</Text></View>
      <View style={{ flex: 1 }}>
        <Text style={s.rowN}>{title}</Text>
        {detail ? <Text style={s.rowD}>{detail}</Text> : null}
      </View>
    </>
  );
  const style = [s.row, tone === "ask" && s.rowAsk, tone === "out" && s.rowOut, selected && s.rowSel, disabled && { opacity: 0.5 }];
  if (!onPress) return <View style={style}>{body}</View>;
  return (
    <Pressable accessibilityRole="button" accessibilityState={{ selected: !!selected, disabled: !!disabled }}
               disabled={disabled} onPress={onPress} style={style}>{body}</Pressable>
  );
}

export function Sev({ severity }: { severity: Severity }) {
  const c = severityStyle[severity];
  return (
    <View style={[s.sev, { backgroundColor: c.bg, borderColor: c.line }]}>
      <Text style={[s.sevText, { color: c.fg }]}>{severity.toUpperCase()}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  h: { fontFamily: font.display, fontSize: size.md, letterSpacing: -0.4, color: color.ink, marginBottom: space.s2 },
  p: { fontFamily: font.body, fontSize: size.sm, lineHeight: 22, color: color.ink3, marginBottom: space.s4 },
  muted: { fontFamily: font.body, fontSize: size.xs, lineHeight: 17, color: color.muted },
  eyebrow: { fontFamily: font.bodySemi, fontSize: size.xs, letterSpacing: 1.5, color: color.muted2, textTransform: "uppercase" },
  pair: { fontFamily: font.display, fontSize: size.sm, color: color.ink },
  mech: { fontFamily: font.body, fontSize: size.xs, lineHeight: 17, color: color.ink3 },
  mono: { fontFamily: font.mono, fontSize: size.xs, lineHeight: 19, color: color.wireText },

  btn: { minHeight: 46, paddingHorizontal: space.s5, borderRadius: radius.pill, borderWidth: 1,
         borderColor: color.ink, alignItems: "center", justifyContent: "center" },
  btn_ink: { backgroundColor: color.ink },
  btn_lime: { backgroundColor: color.lime },
  btn_ghost: { backgroundColor: "transparent" },
  btnPressed: { opacity: 0.85 },
  btnDisabled: { opacity: 0.4 },
  btnText: { fontFamily: font.bodySemi, fontSize: size.sm },

  note: { borderWidth: 1, borderRadius: radius.ctrl, paddingVertical: 10, paddingHorizontal: space.s3, marginBottom: 7 },

  row: { flexDirection: "row", alignItems: "center", gap: space.s3, paddingVertical: 11, paddingHorizontal: space.s3,
         borderWidth: 1, borderColor: color.border, borderRadius: radius.ctrl, marginBottom: 7, backgroundColor: color.paper },
  rowAsk: { borderColor: color.warn, backgroundColor: color.warnWash },
  rowOut: { borderStyle: "dashed", opacity: 0.75 },
  rowSel: { borderColor: color.ink, borderWidth: 2, opacity: 1 },
  rowIc: { width: 26, height: 26, borderRadius: 6, backgroundColor: color.surface2, alignItems: "center", justifyContent: "center" },
  rowIcText: { fontFamily: font.monoMedium, fontSize: size.xs, color: color.ink },
  rowN: { fontFamily: font.bodySemi, fontSize: size.sm, color: color.ink },
  rowD: { fontFamily: font.body, fontSize: size.xs, color: color.muted },

  sev: { alignSelf: "flex-start", borderWidth: 1, borderRadius: 4, paddingHorizontal: 7, paddingVertical: 2 },
  sevText: { fontFamily: font.monoMedium, fontSize: size.xs, letterSpacing: 0.4 },
});
