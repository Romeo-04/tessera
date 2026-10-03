import { useEffect, useState } from "react";
import type { Mode } from "../App";
import { Bell, Out } from "../components/Icons";
import { fetchAlerts } from "../lib/api";
import type { Drug } from "../lib/types";
import { type AlertsFile, watchView } from "../lib/watch";

export function Watch({ mode, drugs }: { mode: Mode; drugs: Drug[] }) {
  const [file, setFile] = useState<AlertsFile | null | "loading">("loading");
  const coded = drugs.filter((d) => d.rxcui);
  const codes = coded.map((d) => d.rxcui as string);
  const names = new Map(coded.map((d) => [d.rxcui, d.display_name ?? d.raw_name]));

  useEffect(() => {
    let alive = true;
    fetchAlerts().then((f) => { if (alive) setFile(f); });
    return () => { alive = false; };
  }, []);

  const view = file === "loading" ? null : watchView(file, codes);

  return (
    <>
      <p className="ph-p">
        A one-time check goes stale: FDA safety communications are published continuously. The
        server watches every drug Tessera covers, and this page picks out the {codes.length} on
        your list — so the server never learns whose list it is.
      </p>

      {file === "loading" && <div className="note">Checking for FDA safety communications…</div>}

      {view?.kind === "unreachable" && (
        <div className="note">
          The watcher runs on Tessera's server, and this {mode === "demo" ? "demo deployment" : "connection"} cannot
          reach it, so nothing has been checked. Nothing on this page is invented to fill the gap.
        </div>
      )}

      {view?.kind === "never_run" && (
        <div className="note note--warn">
          The watcher has not run on this server yet, so these medications have not been checked
          for safety communications.
        </div>
      )}

      {view?.kind === "ran" && view.unchecked.length > 0 && (
        <div className="note note--warn">
          The last watch run ({view.generatedAt.slice(0, 10)}) could not check:{" "}
          {view.unchecked.map((c) => names.get(c) ?? c).join(", ")}. No news is not good news for these.
        </div>
      )}

      {view?.kind === "ran" && view.clear && (
        <div className="note note--lime">
          No FDA safety communications turned up for these medications in the last watch run
          ({view.generatedAt.slice(0, 10)}). It is a search of fda.gov, not a guarantee.
        </div>
      )}

      {view?.kind === "ran" && view.alerts.map((a) => (
        <article className="notif" key={a.url + a.rxcui}>
          <div className="eyebrow" style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <Bell /> {names.get(a.rxcui) ?? a.rxcui}{a.published ? ` · ${a.published}` : ""}
          </div>
          <div className="row__n" style={{ margin: "6px 0 4px" }}>{a.title}</div>
          <p className="ph-muted">{a.summary}</p>
          <a className="srcbtn" style={{ marginTop: 8 }} href={a.url} target="_blank" rel="noopener noreferrer">
            Read it on fda.gov <Out size={12} />
          </a>
        </article>
      ))}

      <ul style={{ padding: 0, listStyle: "none", margin: "16px 0 0" }}>
        {coded.map((d) => (
          <li className="row" key={d.rxcui}>
            <div className="row__ic" aria-hidden="true"><Bell /></div>
            <div><div className="row__n">{d.display_name ?? d.raw_name}</div><div className="row__d">{d.rxcui}</div></div>
          </li>
        ))}
      </ul>
    </>
  );
}
