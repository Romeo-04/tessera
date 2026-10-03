import { useRef } from "react";

const HEIGHTS = [74, 92, 66, 84, 70, 88, 62];

interface Props {
  live: boolean;
  notice: string | null;
  onDemo: () => void;
  onPhotos: (files: File[]) => void;
}

export function Capture({ live, notice, onDemo, onPhotos }: Props) {
  const input = useRef<HTMLInputElement>(null);

  return (
    <>
      <div className="vf" aria-hidden="true">
        <div className="vf__grid" />
        <div className="bottles">
          {HEIGHTS.map((h, i) => (
            <div className="bcell" key={i}>
              <div className="bottle" style={{ height: h }} />
              <div className="vf__box"><span>{i + 1}</span></div>
            </div>
          ))}
        </div>
        <div className="vf__hint">One photo can hold every bottle</div>
      </div>

      <div className="stack">
        <p className="ph-h" style={{ marginBottom: 0 }}>Check a medication list</p>
        <p className="ph-p" style={{ marginBottom: 4 }}>
          Photograph the bottles with the labels facing the camera. Tessera reads them, asks
          when it is unsure, and shows what the FDA labels document — with the source.
        </p>

        {notice && <div className="note note--warn" role="status">{notice}</div>}

        <button className="btn btn--lime btn--block" onClick={onDemo}>
          See it with seven real medications
        </button>

        <input
          ref={input} type="file" accept="image/jpeg,image/png,image/webp"
          multiple hidden
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []).slice(0, 8);
            e.target.value = "";
            if (files.length) onPhotos(files);
          }}
        />
        <button
          className="btn btn--ghost btn--block"
          aria-disabled={!live}
          onClick={() => live && input.current?.click()}
        >
          Photograph your own bottles
        </button>
        <p className="ph-muted" style={{ textAlign: "center" }}>
          {live
            ? "Up to 8 photos. They are read once and deleted; only drug codes reach the reasoning service."
            : "Live checking is off on this deployment, so photos cannot be read here. The demo uses the same label corpus."}
        </p>
      </div>
    </>
  );
}
