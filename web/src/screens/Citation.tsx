import { useState } from "react";
import { Out } from "../components/Icons";
import { citeExcerpt } from "../lib/cite";
import { demoHighlight } from "../lib/session";
import type { RankedRisk } from "../lib/types";
import { pairLabel } from "./Results";

export function Citation({ risk, demo }: { risk: RankedRisk; demo: boolean }) {
  const [full, setFull] = useState(false);
  const quote = risk.quote ?? "";
  const excerpt = citeExcerpt(
    quote, demo ? demoHighlight(risk.span_id) : null,
    [risk.object_name, risk.subject_name].filter((n): n is string => !!n),
  );
  const source = risk.subject_name ? `From the ${risk.subject_name.toLowerCase()} label` : "From the FDA label";

  return (
    <>
      <div className="risk__top"><span className={`sev sev--${risk.severity}`}>{risk.severity}</span></div>
      <p className="ph-h" style={{ marginTop: 6 }}>{pairLabel(risk)}</p>
      <p className="ph-p">{risk.mechanism}</p>

      {quote ? (
        <>
          <span className="eyebrow">{source}</span>
          <blockquote className="quote">
            {full ? quote : (<>“{excerpt.pre}{excerpt.mark && <mark>{excerpt.mark}</mark>}{excerpt.post}”</>)}
          </blockquote>
          {quote.length > excerpt.pre.length + excerpt.mark.length + excerpt.post.length && (
            <button className="linkbtn" style={{ marginBottom: 12 }} onClick={() => setFull((f) => !f)}>
              {full ? "Show the relevant part" : "Show the whole cited passage"}
            </button>
          )}
        </>
      ) : (
        <div className="note">The cited passage is on the label page linked below.</div>
      )}

      <div>
        <a className="srcbtn" href={risk.source_url} target="_blank" rel="noopener noreferrer">
          Open the label on DailyMed <Out size={12} />
        </a>
      </div>

      <div className="note note--lime" style={{ marginTop: 16 }}>
        <strong>What to do:</strong> {risk.action} Tessera never tells you to change a dose.
      </div>
      <p className="ph-muted">
        {demo
          ? "In this demo the sentence was written by hand from the highlighted passage, and the "
            + "build fails if that passage is not verbatim in the label. Live, a separate model "
            + "check verifies each sentence against its passage."
          : "This sentence was written only from the passage above, and a separate check confirmed "
            + "the passage supports it. Sentences that fail that check are removed, not flagged."}
      </p>
    </>
  );
}
