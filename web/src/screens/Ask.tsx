import { useState } from "react";
import { screenQuestion } from "../lib/guardrail";
import type { Drug, SessionResult } from "../lib/types";
import { pairLabel } from "./Results";

type Turn =
  | { who: "me"; text: string }
  | { who: "app"; kind: "answer" | "clarify" | "refuse" | "urgent"; text: string; cite?: string };

const SUGGESTED = [
  "Can he take the water pill with the blood pressure one?",
  "Is the blood thinner OK with the cholesterol one?",
  "Should I lower his warfarin dose until we see the doctor?",
];

/** Answers are assembled from already-cited risks. Nothing here writes new text about drugs. */
function respond(q: string, drugs: Drug[], result: SessionResult): Turn[] {
  const s = screenQuestion(q, drugs);
  if (s.kind === "urgent" || s.kind === "refuse") return [{ who: "app", kind: s.kind, text: s.message }];
  if (s.kind === "clarify") return [{ who: "app", kind: "clarify", text: s.message }];

  const asked = new Set(s.codes);
  const names = drugs.filter((d) => d.rxcui && asked.has(d.rxcui)).map((d) => d.display_name ?? d.raw_name);
  const hits = result.risks.filter((r) => asked.has(r.subject) && asked.has(r.object));
  if (hits.length === 0) {
    return [{
      who: "app", kind: "answer",
      text: `${names.join(", ")}: nothing in the results above documents an interaction between `
        + "these. That is not the same as safe — the results show at most five risks, and labels "
        + "do not cover everything. A pharmacist can check.",
    }];
  }
  return [
    ...hits.map((r): Turn => ({ who: "app", kind: "answer", text: `${pairLabel(r)}: ${r.mechanism}`, cite: r.source_url })),
    { who: "app", kind: "answer", text: "Whether that matters for the person taking them is a question for their pharmacist — bring this list." },
  ];
}

export function Ask({ drugs, result }: { drugs: Drug[]; result: SessionResult }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");

  const ask = (question: string) => {
    const text = question.trim();
    if (!text) return;
    setTurns((t) => [...t, { who: "me", text }, ...respond(text, drugs, result)]);
    setQ("");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100%" }}>
      <p className="ph-p">
        Ask about two medications on this list. Answers come only from the cited results — and
        some questions Tessera will not answer at all.
      </p>
      {turns.length === 0 && (
        <div className="suggest" aria-label="Suggested questions">
          {SUGGESTED.map((s) => <button key={s} onClick={() => ask(s)}>{s}</button>)}
        </div>
      )}

      <div role="log" aria-live="polite">
        {turns.map((t, i) => t.who === "me" ? (
          <div className="bubble bubble--me" key={i}>{t.text}</div>
        ) : t.kind === "refuse" || t.kind === "urgent" ? (
          <div className="refuse" key={i}>
            <div className="refuse__t">{t.kind === "urgent" ? "Get help now" : "Tessera will not answer that"}</div>
            <p style={{ fontSize: "var(--t-sm)", color: "var(--ink-3)" }}>{t.text}</p>
          </div>
        ) : (
          <div className="bubble bubble--app" key={i}>
            {t.text}
            {t.cite && (
              <div className="risk__cite"><a href={t.cite} target="_blank" rel="noopener noreferrer"
                style={{ color: "inherit" }}>FDA label · source</a></div>
            )}
          </div>
        ))}
      </div>

      <form className="askbar" style={{ margin: "auto -16px -16px", position: "sticky", bottom: -16, background: "var(--paper)" }}
            onSubmit={(e) => { e.preventDefault(); ask(q); }}>
        <label className="sr-only" htmlFor="q">Your question</label>
        <input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Type a question" autoComplete="off" />
        <button className="btn" type="submit" style={{ padding: "10px 16px" }}>Ask</button>
      </form>
    </div>
  );
}
