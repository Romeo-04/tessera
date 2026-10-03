import { Out } from "../components/Icons";
import { statusCopy } from "../lib/status";
import type { RankedRisk, SessionResult } from "../lib/types";

export function pairLabel(r: RankedRisk): string {
  return `${r.subject_name ?? r.subject} + ${r.object_name ?? r.object}`;
}

interface Props {
  result: SessionResult;
  notice: string | null;
  onOpen: (index: number) => void;
}

export function Results({ result, notice, onOpen }: Props) {
  const { title, body } = statusCopy(result.status, result.risks.length);
  const unchecked = result.unchecked_drugs.length;

  return (
    <>
      <p className="ph-h">{title}</p>
      <p className="ph-p" style={{ marginBottom: 12 }}>{body}</p>
      {notice && <div className="note note--warn" role="status">{notice}</div>}

      {result.notes.map((n) => (
        <div className={`note${result.status === "ok" ? "" : " note--warn"}`} key={n}>{n}</div>
      ))}

      <ol style={{ listStyle: "none", padding: 0, margin: "12px 0 0" }}>
        {result.risks.map((r, i) => (
          <li key={r.span_id + i}>
            <button className="risk reveal" style={{ animationDelay: `${i * 70}ms` }} onClick={() => onOpen(i)}>
              <div className="risk__top"><span className={`sev sev--${r.severity}`}>{r.severity}</span></div>
              <div className="risk__pair">{pairLabel(r)}</div>
              <p className="risk__mech">{r.mechanism}</p>
              <div className="risk__cite"><Out /> FDA label · read the source</div>
            </button>
          </li>
        ))}
      </ol>

      {unchecked > 0 && (
        <div className="note">
          {unchecked} medication{unchecked === 1 ? " is" : "s are"} recognised but Tessera holds
          no label evidence for {unchecked === 1 ? "it" : "them"}, so {unchecked === 1 ? "it was" : "they were"} not checked.
        </div>
      )}
      <div className="note note--lime">
        Tessera shows what FDA labels document and cites them. It is not medical advice and never
        recommends a dose change — take this list to a pharmacist.
      </div>
    </>
  );
}
