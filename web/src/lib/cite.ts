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

export function citeExcerpt(text: string, highlight: string | null, names: string[]): Excerpt {
  if (highlight) {
    const at = text.indexOf(highlight);
    if (at >= 0) return around(text, at, at + highlight.length);
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
