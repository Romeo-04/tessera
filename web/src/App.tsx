import { useCallback, useEffect, useRef, useState } from "react";
import { Mark } from "./components/Icons";
import { Panel } from "./components/Panel";
import { assessLive, liveAvailable, readLive } from "./lib/api";
import {
  assessDemo, codeSetFor, combine, demoAmbiguities, demoDrugs, rejoinNames,
} from "./lib/session";
import type { Ambiguity, Candidate, Drug, SessionResult, WireEntry } from "./lib/types";
import { Ask } from "./screens/Ask";
import { Capture } from "./screens/Capture";
import { Citation } from "./screens/Citation";
import { Confirm } from "./screens/Confirm";
import { Reading } from "./screens/Reading";
import { Results } from "./screens/Results";
import { Watch } from "./screens/Watch";

export type Screen = "capture" | "reading" | "confirm" | "results" | "citation" | "ask" | "watch";
export type Mode = "demo" | "live";

const TITLES: Record<Screen, string> = {
  capture: "Tessera", reading: "Reading labels", confirm: "One thing to check",
  results: "What to raise", citation: "Source", ask: "Ask", watch: "Watching",
};

export default function App() {
  const [mode, setMode] = useState<Mode>("demo");
  const [live, setLive] = useState(false);
  const [screen, setScreen] = useState<Screen>("capture");
  const [drugs, setDrugs] = useState<Drug[]>([]);
  const [ambiguities, setAmbiguities] = useState<Ambiguity[]>([]);
  const [choices, setChoices] = useState<Record<string, Candidate | null>>({});
  const [excluded, setExcluded] = useState<string[]>([]);
  const [result, setResult] = useState<SessionResult | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [wire, setWire] = useState<WireEntry[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const screenRef = useRef<HTMLDivElement>(null);

  useEffect(() => { liveAvailable().then(setLive); }, []);

  // Move focus to the new screen so keyboard and screen-reader users land on it.
  useEffect(() => { screenRef.current?.focus(); screenRef.current?.scrollTo(0, 0); }, [screen]);

  const reset = useCallback(() => {
    setScreen("capture"); setDrugs([]); setAmbiguities([]); setChoices({});
    setExcluded([]); setResult(null); setSelected(null); setWire([]); setNotice(null);
  }, []);

  const startDemo = useCallback((reason: string | null = null) => {
    reset();
    setMode("demo");
    setNotice(reason);
    setDrugs(demoDrugs());
    setAmbiguities(demoAmbiguities());
    setWire([{
      boundary: "photos", method: "POST", url: "Token Factory · Nemotron 3 Nano Omni",
      body: "content: [ 7 × image_url ]\n// demo: nothing was sent", sent: false,
    }]);
    setScreen("reading");
  }, [reset]);

  const startLive = useCallback(async (files: File[]) => {
    reset();
    setMode("live");
    setBusy(true);
    setScreen("reading");
    const kb = Math.round(files.reduce((n, f) => n + f.size, 0) / 1024);
    setWire([{
      boundary: "photos", method: "POST", url: "/api/read → Nemotron 3 Nano Omni",
      body: `photos: ${files.length} × image, ${kb} KB\n// deleted on the server after the call`,
      sent: true,
    }]);
    const r = await readLive(files);
    setBusy(false);
    if (!r.ok) {
      if (r.fallback) return startDemo(`${r.reason} Showing the demo instead — nothing about your photos.`);
      setNotice(r.reason);
      setScreen("capture");
      return;
    }
    if (r.value.unreadable) {
      setResult({
        risks: [], excluded_drugs: [], unchecked_drugs: [], needs_confirmation: [],
        status: "no_drugs_detected", notes: [],
      });
      setScreen("results");
      return;
    }
    setDrugs(r.value.drugs.filter((d) => d.in_formulary || d.rxcui === null));
    setExcluded(r.value.excluded);
    setAmbiguities(r.value.confirmations);
  }, [reset, startDemo]);

  const codesToCheck = useCallback((): { codes: string[]; names: Drug[]; leftOut: string[] } => {
    const names = drugs.filter((d) => d.rxcui);
    const codes = names.map((d) => d.rxcui as string);
    const leftOut: string[] = [];
    for (const a of ambiguities) {
      const pick = choices[a.raw_name];
      if (!pick) { leftOut.push(a.raw_name); continue; }
      const code = a.ingredient_rxcui ?? pick.rxcui;
      codes.push(code);
      names.push({ raw_name: a.raw_name, strength: null, form: null, rxcui: code,
        display_name: a.ingredient_rxcui ? (drugs.find((d) => d.raw_name === a.raw_name)?.display_name ?? pick.display_name) : pick.display_name });
    }
    return { codes, names, leftOut };
  }, [drugs, ambiguities, choices]);

  const runAssess = useCallback(async () => {
    const { codes, names, leftOut } = codesToCheck();
    const body = JSON.stringify(codeSetFor(codes), null, 2);
    setWire((w) => [...w, {
      boundary: "codes", method: "POST",
      url: mode === "live" ? "/api/assess → reasoning" : "/api/assess → reasoning (demo)",
      body: body + (mode === "demo" ? "\n// demo: answered from the bundled, precomputed result" : ""),
      sent: mode === "live",
    }]);

    if (mode === "demo") {
      setResult(assessDemo(codes));
      setScreen("results");
      return;
    }
    if (codes.length < 2) {
      setResult(combine({
        risks: [], excluded_drugs: [], unchecked_drugs: [], needs_confirmation: [],
        status: "insufficient_drugs",
        notes: ["At least two identified medications are needed to check for interactions."],
      }, { excluded, leftOut }));
      setScreen("results");
      return;
    }
    setBusy(true);
    const r = await assessLive(codes);
    setBusy(false);
    if (!r.ok) {
      if (r.fallback) return startDemo(`${r.reason} Showing the demo instead — nothing about your photos.`);
      setNotice(r.reason);
      return;
    }
    setResult(combine(rejoinNames(r.result, names), { excluded, leftOut }));
    setScreen("results");
  }, [codesToCheck, mode, excluded, startDemo]);

  const afterReading = useCallback(() => {
    if (ambiguities.length > 0) setScreen("confirm");
    else void runAssess();
  }, [ambiguities, runAssess]);

  const decide = useCallback((rawName: string, pick: Candidate | null) => {
    setChoices((c) => ({ ...c, [rawName]: pick }));
  }, []);

  const allDecided = ambiguities.every((a) => a.raw_name in choices);
  const checkedDrugs = codesToCheck().names;

  const tabbed = screen === "results" || screen === "ask" || screen === "watch";

  return (
    <div className="sheet">
      <header className="top">
        <span className="brand"><Mark /> Tessera</span>
        <span className={`chip${mode === "demo" ? " chip--lime" : ""}`}>
          <span className={`chip__dot${mode === "live" ? " chip__dot--on" : ""}`} aria-hidden="true" />
          {mode === "demo" ? "Seeded demo" : "Live"}
        </span>
        <span className="chip">Real FDA label text</span>
        <p className="tag">
          Photograph the bottles. Get a short, ranked list of documented interaction risks —
          each linked to the FDA label text it came from.
        </p>
      </header>

      <div className="stage">
        <div>
          <div className="phone">
            <div className="phone__notch" aria-hidden="true" />
            <div className="phone__screen">
              <div className="sbar" aria-hidden="true"><span>9:41</span><span>▮▮▮</span></div>
              <div className="appbar">
                {screen === "citation" ? (
                  <button className="linkbtn" onClick={() => setScreen("results")}>← Back</button>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M12 2 4 7v10l8 5 8-5V7l-8-5Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
                  </svg>
                )}
                <h1 className="appbar__t">{TITLES[screen]}</h1>
                {screen !== "capture" && (
                  <button className="linkbtn appbar__end" onClick={reset}>Start over</button>
                )}
              </div>

              <div className="screen" ref={screenRef} tabIndex={-1} aria-live="polite">
                {screen === "capture" && (
                  <Capture live={live} notice={notice} onDemo={() => startDemo()} onPhotos={startLive} />
                )}
                {screen === "reading" && (
                  <Reading mode={mode} busy={busy} drugs={drugs} ambiguities={ambiguities}
                           excluded={excluded} onContinue={afterReading} />
                )}
                {screen === "confirm" && (
                  <Confirm ambiguities={ambiguities} choices={choices} onDecide={decide}
                           ready={allDecided} busy={busy} notice={notice} onContinue={() => void runAssess()} />
                )}
                {screen === "results" && result && (
                  <Results result={result} notice={notice}
                           onOpen={(i) => { setSelected(i); setScreen("citation"); }} />
                )}
                {screen === "citation" && result && selected !== null && result.risks[selected] && (
                  <Citation risk={result.risks[selected]} demo={mode === "demo"} />
                )}
                {screen === "ask" && result && <Ask drugs={checkedDrugs} result={result} />}
                {screen === "watch" && <Watch mode={mode} drugs={checkedDrugs} />}
              </div>

              {tabbed && (
                <nav className="tabs" aria-label="Results">
                  {(["results", "ask", "watch"] as const).map((s) => (
                    <button key={s} className="tab" aria-current={screen === s ? "page" : undefined}
                            onClick={() => setScreen(s)}>
                      {s === "results" ? "Risks" : s === "ask" ? "Ask" : "Watch"}
                    </button>
                  ))}
                </nav>
              )}
            </div>
          </div>
        </div>

        <Panel screen={screen} mode={mode} wire={wire} />
      </div>

      <footer className="foot">
        <span>Tessera · Personal AI track · Nebius × NVIDIA · Apache-2.0</span>
        <span>Not medical advice, and not a clinical device. It never recommends a dose change.</span>
      </footer>
    </div>
  );
}
