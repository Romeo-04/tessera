/**
 * Cut a cited label span down to the part a caregiver needs to read, with the
 * supporting text marked. Everything returned is a verbatim slice of the
 * source; the ellipses are the only characters added.
 */
export interface Excerpt {
  pre: string;
  mark: string;
  post: string;
}

const CONTEXT = 140;

function sentences(text: string): { start: number; end: number }[] {
  const out: { start: number; end: number }[] = [];
  const re = /[^.;]+[.;]?\s*/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m[0].length === 0) break;
    out.push({ start: m.index, end: m.index + m[0].trimEnd().length });
  }
  return out;
}

function around(text: string, start: number, end: number): Excerpt {
  const from = Math.max(0, start - CONTEXT);
  const to = Math.min(text.length, end + CONTEXT);
  return {
    pre: (from > 0 ? "…" : "") + text.slice(from, start),
    mark: text.slice(start, end),
    post: text.slice(end, to) + (to < text.length ? "…" : ""),
  };
}

export function citeExcerpt(text: string, highlight: string | null, names: string[],
                            classPhrase?: string | null): Excerpt {
  if (highlight) {
    const at = text.indexOf(highlight);
    if (at >= 0) return around(text, at, at + highlight.length);
  }
  if (classPhrase) {
    // The label named a class, not the drug, so the drug name will not be in
    // the passage. The class phrase is, exactly as the label wrote it.
    const phrase = classPhrase.toLowerCase();
    const hit = sentences(text).find((s) => text.slice(s.start, s.end).toLowerCase().includes(phrase));
    if (hit) return around(text, hit.start, hit.end);
  }
  for (const name of names) {
    const word = name.toLowerCase().split(/\s+/)[0];
    if (!word || word.length < 4) continue;
    const re = new RegExp(`\\b${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
    const hit = sentences(text).find((s) => re.test(text.slice(s.start, s.end)));
    if (hit) return around(text, hit.start, hit.end);
  }
  const to = Math.min(text.length, CONTEXT * 2);
  return { pre: text.slice(0, to) + (to < text.length ? "…" : ""), mark: "", post: "" };
}

/**
 * Why a cited passage does not mention the caregiver's drug by name: the
 * label warned about its class. Null for a passage that names the drug.
 */
export function classNote(risk: { via_class?: string | null; subject_name: string | null;
                                  object_name: string | null }): string | null {
  if (!risk.via_class) return null;
  const label = risk.subject_name ? `The ${risk.subject_name.toLowerCase()} label` : "The label";
  const drug = risk.object_name ? risk.object_name.toLowerCase() : "this medication";
  const it = risk.object_name
    ? risk.object_name.charAt(0).toUpperCase() + risk.object_name.slice(1).toLowerCase()
    : "It";
  return `${label} warns about “${risk.via_class}” rather than naming ${drug}. ${it} is one of them.`;
}
