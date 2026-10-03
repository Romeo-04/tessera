import { useEffect, useState } from "react";
import type { Mode } from "../App";
import { Bell, Out } from "../components/Icons";
import { alertsFor, type Alert } from "../lib/api";
import type { Drug } from "../lib/types";

export function Watch({ mode, drugs }: { mode: Mode; drugs: Drug[] }) {
  const [state, setState] = useState<{ generatedAt: string | null; alerts: Alert[] } | null | "loading">("loading");
  const codes = drugs.filter((d) => d.rxcui).map((d) => d.rxcui as string);
  const names = new Map(drugs.map((d) => [d.rxcui, d.display_name ?? d.raw_name]));

  useEffect(() => {
    let live = true;
    alertsFor(codes).then((r) => { if (live) setState(r); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [codes.join(",")]);

  return (
    <>
      <p className="ph-p">
        A one-time check goes stale: FDA safety communications are published continuously. The
        server watches every drug Tessera covers, and this page picks out the {codes.length} on
        your list — so the server never learns whose list it is.
      </p>

      {state === "loading" && <div className="note">Checking for new safety communications…</div>}

      {state === null && (
        <div className="note">
          The watcher runs on Tessera's server, and this {mode === "demo" ? "demo deployment" : "connection"} cannot
          reach it, so there is nothing to show. Nothing on this page is invented to fill the gap.
        </div>
      )}

      {state !== null && state !== "loading" && state.alerts.length === 0 && (
        <div className="note note--lime">
          No new FDA safety communications for these medications
          {state.generatedAt ? ` as of ${state.generatedAt.slice(0, 10)}` : ""}.
        </div>
      )}

      {state !== null && state !== "loading" && state.alerts.map((a) => (
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
        {drugs.filter((d) => d.rxcui).map((d) => (
          <li className="row" key={d.rxcui}>
            <div className="row__ic" aria-hidden="true"><Bell /></div>
            <div><div className="row__n">{d.display_name ?? d.raw_name}</div><div className="row__d">{d.rxcui}</div></div>
          </li>
        ))}
      </ul>
    </>
  );
}
