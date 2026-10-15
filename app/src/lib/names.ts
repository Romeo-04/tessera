import type { ReadResult } from "./api";

/**
 * RxNorm writes ingredients in lower case ("lisinopril"), so live results read
 * "lisinopril + metformin" while the demo reads "Lisinopril + Metformin". A
 * name that already has a capital in it is left exactly as it is: "WARF SOD"
 * is what the bottle said, and rewriting it would hide that.
 */
export function drugName<T extends string | null>(name: T): T {
  if (!name || /[A-Z]/.test(name)) return name;
  return (name.charAt(0).toUpperCase() + name.slice(1)) as T;
}

/** The server's reading with every name written one way. Codes are untouched. */
export function tidyRead(read: ReadResult): ReadResult {
  return {
    ...read,
    drugs: read.drugs.map((d) => ({ ...d, display_name: drugName(d.display_name) })),
    confirmations: read.confirmations.map((c) => ({
      ...c,
      options: c.options.map((o) => ({ ...o, display_name: drugName(o.display_name) })),
    })),
  };
}

/**
 * One line for a result card whose label named the drug's class rather than
 * the drug, so the card does not read as if the label named it. The citation
 * screen says the longer version.
 */
export function classLine(risk: { via_class?: string | null }): string | null {
  return risk.via_class
    ? `The label warns about “${risk.via_class}”, which includes this drug.`
    : null;
}
