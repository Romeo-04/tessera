import { router } from "expo-router";
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
  type ReactNode,
} from "react";
import { assessLive, liveAvailable, readLive, type PhotoInput } from "../lib/api";
import {
  assessDemo, codeSetFor, combine, demoAmbiguities, demoDrugs, rejoinNames,
} from "../lib/session";
import type { Ambiguity, Candidate, Drug, SessionResult, WireEntry } from "../lib/types";

export type Mode = "demo" | "live";

const EMPTY: SessionResult = {
  risks: [], excluded_drugs: [], unchecked_drugs: [], needs_confirmation: [], status: "ok", notes: [],
};

interface Session {
  mode: Mode;
  live: boolean;
  busy: boolean;
  notice: string | null;
  drugs: Drug[];
  ambiguities: Ambiguity[];
  choices: Record<string, Candidate | null>;
  excluded: string[];
  result: SessionResult | null;
  wire: WireEntry[];
  /** Every drug that was actually checked, named - the list the Watch tab and saving use. */
  checked: Drug[];
  startDemo: (reason?: string | null) => void;
  startLive: (photos: PhotoInput[]) => Promise<void>;
  recheck: (drugs: Drug[]) => Promise<void>;
  decide: (rawName: string, pick: Candidate | null) => void;
  runAssess: () => Promise<void>;
  afterReading: () => void;
  reset: () => void;
}

const Ctx = createContext<Session | null>(null);

export function useSession(): Session {
  const s = useContext(Ctx);
  if (!s) throw new Error("useSession outside SessionProvider");
  return s;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>("demo");
  const [live, setLive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [drugs, setDrugs] = useState<Drug[]>([]);
  const [ambiguities, setAmbiguities] = useState<Ambiguity[]>([]);
  const [choices, setChoices] = useState<Record<string, Candidate | null>>({});
  const [excluded, setExcluded] = useState<string[]>([]);
  const [result, setResult] = useState<SessionResult | null>(null);
  const [wire, setWire] = useState<WireEntry[]>([]);
  // Bumped by every new check: a response that arrives for an abandoned one is dropped.
  const session = useRef(0);

  useEffect(() => { liveAvailable().then(setLive); }, []);

  const clear = useCallback(() => {
    session.current += 1;
    setBusy(false); setNotice(null); setDrugs([]); setAmbiguities([]); setChoices({});
    setExcluded([]); setResult(null); setWire([]);
  }, []);

  const reset = useCallback(() => {
    clear();
    router.dismissTo("/");
  }, [clear]);

  const startDemo = useCallback((reason: string | null = null) => {
    clear();
    setMode("demo");
    setNotice(reason);
    setDrugs(demoDrugs());
    setAmbiguities(demoAmbiguities());
    setWire([{
      boundary: "photos", method: "POST", url: "Token Factory · Nemotron 3 Nano Omni",
      body: "content: [ 7 × image_url ]\n// demo: nothing was sent", sent: false,
    }]);
    router.push("/reading");
  }, [clear]);

  const fallBack = useCallback((reason: string) => {
    startDemo(`${reason} Showing the demo instead — nothing about your own medications.`);
  }, [startDemo]);

  const startLive = useCallback(async (photos: PhotoInput[]) => {
    clear();
    setMode("live");
    setBusy(true);
    router.push("/reading");
    const kb = Math.round(photos.reduce((n, p) => n + (p.bytes ?? 0), 0) / 1024);
    setWire([{
      boundary: "photos", method: "POST", url: "/api/read → Nemotron 3 Nano Omni",
      body: `photos: ${photos.length} × image${kb ? `, ${kb} KB` : ""}\n// deleted on the server after the call`,
      sent: true,
    }]);
    const mine = session.current;
    const r = await readLive(photos);
    if (mine !== session.current) return;
    setBusy(false);
    if (!r.ok) {
      if (r.fallback) return fallBack(r.reason);
      setNotice(r.reason);
      return;
    }
    if (r.value.unreadable) {
      setResult({ ...EMPTY, status: "no_drugs_detected" });
      router.replace("/risks");
      return;
    }
    // Out-of-scope drugs are listed once, under "excluded", not also as a question.
    setDrugs(r.value.drugs.filter((d) => d.in_formulary));
    setExcluded(r.value.excluded);
    setAmbiguities(r.value.confirmations);
  }, [clear, fallBack]);

  const resolved = useCallback((): { codes: string[]; names: Drug[]; leftOut: string[] } => {
    const names = drugs.filter((d) => d.rxcui);
    const codes = names.map((d) => d.rxcui as string);
    const leftOut: string[] = [];
    for (const a of ambiguities) {
      const pick = choices[a.raw_name];
      if (!pick) { leftOut.push(a.raw_name); continue; }
      codes.push(pick.rxcui);
      names.push({ raw_name: a.raw_name, strength: null, form: null, rxcui: pick.rxcui,
        display_name: pick.display_name });
    }
    return { codes, names, leftOut };
  }, [drugs, ambiguities, choices]);

  const assessCodes = useCallback(async (
    m: Mode, codes: string[], names: Drug[], local: { excluded: string[]; leftOut: string[] },
  ) => {
    setWire((w) => [...w, {
      boundary: "codes", method: "POST",
      url: m === "live" ? "/api/assess → reasoning" : "/api/assess → reasoning (demo)",
      body: JSON.stringify(codeSetFor(codes), null, 2)
        + (m === "demo" ? "\n// demo: answered from the bundled, precomputed result" : ""),
      sent: m === "live",
    }]);

    if (m === "demo") {
      setResult(assessDemo(codes));
      router.replace("/risks");
      return;
    }
    if (codes.length < 2) {
      setResult(combine({
        ...EMPTY, status: "insufficient_drugs",
        notes: ["At least two identified medications are needed to check for interactions."],
      }, local));
      router.replace("/risks");
      return;
    }
    setBusy(true);
    setNotice(null);
    const mine = session.current;
    const r = await assessLive(codes);
    if (mine !== session.current) return;
    setBusy(false);
    if (!r.ok) {
      if (r.fallback) return fallBack(r.reason);
      setNotice(r.reason);
      return;
    }
    setResult(combine(rejoinNames(r.result, names), local));
    router.replace("/risks");
  }, [fallBack]);

  const runAssess = useCallback(async () => {
    const { codes, names, leftOut } = resolved();
    await assessCodes(mode, codes, names, { excluded, leftOut });
  }, [resolved, assessCodes, mode, excluded]);

  /** Re-check a saved list: codes only, no photographs, no perception call. */
  const recheck = useCallback(async (saved: Drug[]) => {
    clear();
    const m: Mode = live ? "live" : "demo";
    setMode(m);
    setDrugs(saved);
    const codes = saved.filter((d) => d.rxcui).map((d) => d.rxcui as string);
    if (m === "demo") {
      try {
        assessDemo(codes);
      } catch {
        setNotice("Live checking is off here, and the demo only knows its own seven "
          + "medications, so this saved list cannot be checked on this deployment.");
        setResult({ ...EMPTY, status: "insufficient_drugs", notes: [] });
        router.push("/risks");
        return;
      }
    }
    router.push("/reading");
    await assessCodes(m, codes, saved, { excluded: [], leftOut: [] });
  }, [clear, live, assessCodes]);

  const afterReading = useCallback(() => {
    if (ambiguities.length > 0) router.push("/confirm");
    else void runAssess();
  }, [ambiguities, runAssess]);

  const decide = useCallback((rawName: string, pick: Candidate | null) => {
    setChoices((c) => ({ ...c, [rawName]: pick }));
  }, []);

  const value = useMemo<Session>(() => ({
    mode, live, busy, notice, drugs, ambiguities, choices, excluded, result, wire,
    checked: resolved().names,
    startDemo, startLive, recheck, decide, runAssess, afterReading, reset,
  }), [mode, live, busy, notice, drugs, ambiguities, choices, excluded, result, wire, resolved,
    startDemo, startLive, recheck, decide, runAssess, afterReading, reset]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
