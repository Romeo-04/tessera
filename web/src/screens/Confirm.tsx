import type { Ambiguity, Candidate } from "../lib/types";

interface Props {
  ambiguities: Ambiguity[];
  choices: Record<string, Candidate | null>;
  onDecide: (rawName: string, pick: Candidate | null) => void;
  ready: boolean;
  busy: boolean;
  notice: string | null;
  onContinue: () => void;
}

export function Confirm({ ambiguities, choices, onDecide, ready, busy, notice, onContinue }: Props) {
  return (
    <>
      <p className="ph-p">
        We could not tell {ambiguities.length === 1 ? "these" : "some of these"} apart. Rather
        than guess, we are asking.
      </p>

      {ambiguities.map((a) => {
        const decided = a.raw_name in choices;
        const pick = choices[a.raw_name];
        return (
          <fieldset key={a.raw_name} style={{ border: 0, padding: 0, margin: "0 0 16px" }}>
            <legend className="note note--warn" style={{ width: "100%" }}>
              The label read <strong>{a.raw_name}</strong>.
              {a.margin !== undefined
                ? ` The best two matches scored within ${a.margin.toFixed(3)} of each other — inside our margin.`
                : " No match was clearly ahead."}
            </legend>
            {a.options.map((o, i) => {
              const unavailable = a.precomputed !== undefined && !a.precomputed.includes(o.rxcui);
              return (
              <button
                key={o.rxcui} className="row" aria-pressed={pick?.rxcui === o.rxcui}
                disabled={unavailable}
                style={pick?.rxcui === o.rxcui ? { borderColor: "var(--ink)", boxShadow: "inset 0 0 0 1px var(--ink)" } : undefined}
                onClick={() => onDecide(a.raw_name, o)}
              >
                <div className="row__ic" aria-hidden="true">{pick?.rxcui === o.rxcui ? "✓" : i + 1}</div>
                <div><div className="row__n">{o.display_name}</div>
                  <div className="row__d">{o.rxcui} · match {o.score.toFixed(3)}{unavailable ? " · demo has no precomputed answer" : ""}</div></div>
              </button>
              );
            })}
            <button
              className="row row--out" aria-pressed={decided && pick === null}
              style={decided && pick === null ? { opacity: 1, borderColor: "var(--ink)" } : undefined}
              onClick={() => onDecide(a.raw_name, null)}
            >
              <div className="row__ic" aria-hidden="true">{decided && pick === null ? "✓" : "–"}</div>
              <div><div className="row__n">Not sure — leave it out</div>
                <div className="row__d">It will not be checked, and the result will say so</div></div>
            </button>
          </fieldset>
        );
      })}

      <div className="note note--lime">
        Until you choose, this medication carries no code — so nothing downstream can score it.
        An unanswered question is safer than a confident wrong answer.
      </div>
      {notice && <div className="note note--warn" role="status">{notice}</div>}

      <button className="btn btn--block" disabled={!ready || busy} onClick={onContinue}>
        {busy ? "Checking…" : "Check for interactions"}
      </button>
    </>
  );
}
