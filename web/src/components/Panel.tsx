import type { Mode, Screen } from "../App";
import type { WireEntry } from "../lib/types";

const ALL_TIERS = ["OMNI", "CHEAP", "TOOL", "DEEP"] as const;

const NARRATION: Record<Screen, { title: string; body: string; tiers: string[] }> = {
  capture: {
    title: "One photo, every bottle",
    body: "A caregiver with a shoebox of a parent's medications is never going to type seven "
      + "drug names, spelled correctly, into a form. So the whole input is a photograph.",
    tiers: [],
  },
  reading: {
    title: "One model reads every label",
    body: "Nemotron 3 Nano Omni reads all the photos in a single call and keeps one context "
      + "across them, so two shots of the same bottle are recognised as one drug. Each name is "
      + "then normalised to an RxNorm code — or deliberately left without one.",
    tiers: ["OMNI"],
  },
  confirm: {
    title: "Abstaining, for real",
    body: "When two candidates score too close to call, the drug gets no code at all. A code "
      + "that does not exist cannot cross the gate, so no risk can be built from a medication "
      + "the system has just admitted it cannot name.",
    tiers: ["OMNI"],
  },
  results: {
    title: "A few, not fourteen",
    body: "A deterministic table — derived once from FDA label text and frozen — finds the "
      + "documented pairs. Code ranks them by the label's own severity wording and caps the "
      + "list at five, stating the count. Nemotron Ultra writes each explanation only from "
      + "the cited passage; a separate check drops any sentence the passage does not support.",
    tiers: ["DEEP", "TOOL"],
  },
  citation: {
    title: "Every claim, traceable",
    body: "The passage below the sentence is the evidence, verbatim from the FDA label, with "
      + "a link to the full record on DailyMed. A warning you cannot verify spends the trust "
      + "that makes the verifiable ones worth reading.",
    tiers: ["TOOL"],
  },
  ask: {
    title: "The refusal is code, not a prompt",
    body: "Questions about changing, skipping or stopping a dose are refused by a "
      + "deterministic filter before anything else runs, and emergencies are sent to "
      + "emergency care. Everything else is answered only from the cited results.",
    tiers: [],
  },
  watch: {
    title: "Checked, then kept checked",
    body: "A scheduled job searches FDA safety communications for every drug Tessera covers "
      + "and triages them on the cheapest tier. The browser downloads them all and keeps only "
      + "its own, so the server never pairs a person with a medication list.",
    tiers: ["CHEAP"],
  },
};

function wireTitle(wire: WireEntry[]): { title: string; body: string } {
  const last = wire[wire.length - 1];
  if (!last) {
    return { title: "Nothing yet", body: "No request has been made. Everything so far is on this device." };
  }
  if (last.boundary === "photos") {
    return {
      title: "The photographs",
      body: "The first boundary, stated honestly: perception runs in the cloud today, so the "
        + "images reach Nebius for Omni to read. They are deleted after the call. On-device "
        + "Omni is the intended end state and is not built yet.",
    };
  }
  return {
    title: "Codes. Only codes.",
    body: "This is the boundary the privacy gate governs. The reasoning service receives the "
      + "body below and nothing else — the request schema rejects any other field. Names are "
      + "re-joined here, in the browser, which had them all along.",
  };
}

export function Panel({ screen, mode, wire }: { screen: Screen; mode: Mode; wire: WireEntry[] }) {
  const n = NARRATION[screen];
  const demoNote = mode === "demo" && screen === "results"
    ? " In this demo the ranking and cap are the real code; the explanations were written by hand from each passage, because no model is called."
    : "";
  const w = wireTitle(wire);

  return (
    <aside className="panel" aria-label="How it works">
      <section className="pcard">
        <span className="eyebrow">How it works</span>
        <h3>{n.title}</h3>
        <p>{n.body}{demoNote}</p>
        <div className="tiers" aria-label="Nemotron tiers used at this step">
          {ALL_TIERS.map((t) => (
            <span key={t} className={`tier${n.tiers.includes(t) ? " tier--on" : ""}`}>{t}</span>
          ))}
        </div>
      </section>

      <section className="pcard pcard--dark" aria-live="polite">
        <span className="eyebrow">What crossed the network</span>
        <h3>{w.title}</h3>
        <p>{w.body}</p>
        <div className="wire">
          {wire.length === 0 ? "—" : wire.map((e, i) => (
            <div className="wire__entry" key={i}>
              <span className="c">{e.method} {e.url}{e.sent ? "" : "  (not sent)"}</span>{"\n"}
              {e.boundary === "codes"
                ? e.body.split("\n").map((line, j) => (
                    <span key={j}>{line.startsWith("//") ? <span className="c">{line}</span>
                      : line.replace(/"(codes)"/, "\u0000").split("\u0000").map((part, k, arr) => (
                        <span key={k}>{part}{k < arr.length - 1 && <span className="k">"codes"</span>}</span>
                      ))}{"\n"}</span>
                  ))
                : e.body.split("\n").map((line, j) => (
                    <span key={j} className={line.startsWith("//") ? "c" : undefined}>{line}{"\n"}</span>
                  ))}
            </div>
          ))}
        </div>
      </section>

      <section className="pcard">
        <span className="eyebrow">Grounding</span>
        <h3>{mode === "demo" ? "This scenario is real" : "Where answers come from"}</h3>
        <p>
          {mode === "demo"
            ? "Seven medications typical of heart failure with type 2 diabetes. Every interaction "
              + "shown is documented in the FDA label text in Tessera's corpus, ranked and capped "
              + "by the same code the live service runs. Only the plain-language sentences were "
              + "written for the demo, from the quoted passage alone."
            : "FDA Structured Product Labels from DailyMed, normalised with RxNorm. Drugs outside "
              + "the corpus are reported as unchecked — never as safe."}
        </p>
        <dl className="kv">
          <dt>Formulary</dt><dd>358 chronic-care drugs</dd>
          <dt>With label evidence</dt><dd>285 of 358</dd>
          <dt>Label sections</dt><dd>723</dd>
          <dt>Most risks shown</dt><dd>5, with the total stated</dd>
        </dl>
      </section>
    </aside>
  );
}
