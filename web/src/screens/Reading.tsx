import type { Mode } from "../App";
import type { Ambiguity, Drug } from "../lib/types";

interface Props {
  mode: Mode;
  busy: boolean;
  drugs: Drug[];
  ambiguities: Ambiguity[];
  excluded: string[];
  onContinue: () => void;
}

export function Reading({ mode, busy, drugs, ambiguities, excluded, onContinue }: Props) {
  const unsure = new Set(ambiguities.map((a) => a.raw_name));
  const total = drugs.length + excluded.length;

  return (
    <>
      <p className="ph-h">{busy ? "Reading the labels…" : `Read ${total} label${total === 1 ? "" : "s"}`}</p>
      <div className="mods"><span className="mod">OCR</span><span className="mod">multi-image</span></div>
      <div className={`prog${busy ? " prog--wait" : ""}`}><span /></div>
      <p className="ph-muted" style={{ marginBottom: 16 }}>
        Nemotron 3 Nano Omni · one call for every photo{mode === "demo" ? " · demo" : ""}
      </p>

      {!busy && drugs.map((d, i) => {
        const ask = unsure.has(d.raw_name) || d.rxcui === null;
        return (
          <div className={`row reveal${ask ? " row--ask" : ""}`} key={d.raw_name + i}
               style={{ animationDelay: `${i * 90}ms` }}>
            <div className="row__ic" aria-hidden="true">{ask ? "?" : "✓"}</div>
            <div>
              <div className="row__n">{d.display_name ?? d.raw_name}</div>
              <div className="row__d">
                {ask ? "could not tell which — we will ask" : [d.strength, d.form].filter(Boolean).join(" ") || d.raw_name}
              </div>
            </div>
          </div>
        );
      })}
      {!busy && excluded.map((name) => (
        <div className="row row--out" key={name}>
          <div className="row__ic" aria-hidden="true">–</div>
          <div><div className="row__n">{name}</div><div className="row__d">outside the checked list</div></div>
        </div>
      ))}

      {!busy && (
        <button className="btn btn--block" style={{ marginTop: 12 }} onClick={onContinue}>
          {ambiguities.length ? "Continue" : "Check for interactions"}
        </button>
      )}
    </>
  );
}
