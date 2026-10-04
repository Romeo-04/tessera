import type { Alert } from "./api";

export interface AlertsFile {
  generated_at: string | null;
  alerts: Alert[];
  unchecked?: string[];
}

export type WatchView =
  | { kind: "unreachable" }
  | { kind: "never_run" }
  | { kind: "ran"; generatedAt: string; alerts: Alert[]; unchecked: string[]; clear: boolean };

/**
 * What the Watch tab is allowed to claim. Like every other status in Tessera,
 * absence of data is never rendered as reassurance: "clear" needs a completed
 * run that checked every drug on this list and found nothing.
 */
export function watchView(file: AlertsFile | null, codes: string[]): WatchView {
  if (file === null) return { kind: "unreachable" };
  if (!file.generated_at) return { kind: "never_run" };
  const mine = new Set(codes);
  const alerts = file.alerts.filter((a) => mine.has(a.rxcui));
  const knowsCoverage = Array.isArray(file.unchecked);
  const unchecked = (file.unchecked ?? []).filter((c) => mine.has(c));
  return {
    kind: "ran", generatedAt: file.generated_at, alerts, unchecked,
    clear: knowsCoverage && alerts.length === 0 && unchecked.length === 0,
  };
}
