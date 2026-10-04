# Tessera

**Seven bottles. One sourced list. Every claim traceable to an FDA label.**

Tessera reads a photograph of someone's medications and returns a short, ranked list of
documented interaction risks — each one linked to the FDA-approved label section it came from.

**What the privacy gate actually guarantees today:** the reasoning service — retrieval,
interaction resolution, severity adjudication — receives *only* numeric RxNorm codes. No drug
names, strengths, directions, dates, or images reach it. That boundary is enforced in code
(`src/tessera/privacy.py`) and tested on the serialised payload, not just the object.

**What it does not yet guarantee, stated plainly:** perception currently runs in the cloud, not
on the device. In the web app the photographs go to Tessera's own API (`/api/read`), which sends
them to Nebius for a vision model (MiniCPM-V 4.5) to read, and sends the OCR'd drug name to the
NLM's public RxNorm service. On-device perception is the intended end state and is not built. See
[Deployment honesty](#deployment-honesty).

> A Roman *tessera* was a small token you handed over **instead of** your name. That is exactly
> what the RxNorm code is here.

**Track:** Personal AI · **Built on:** Nebius Token Factory + NVIDIA Nemotron

---

## Try it

**Web demo:** https://tessera-jade-gamma.vercel.app — opens on a **seeded demo**: seven real
medications, real FDA label text, the real resolver and five-risk cap. It needs no camera, no
upload, no account and no credentials, and it makes no model calls — so its plain-language
explanations were written by hand from each quoted passage, and the build fails if a passage is
not verbatim in the label. The right-hand panel shows
the exact JSON the app sends across the privacy gate.

**iOS and Android:** the same Expo (React Native) codebase is a native app with a real camera
and a list saved on the device.

```bash
cd app && npm install
npx expo start            # scan the QR code with Expo Go, or press w for the web build
```

| On the phone | What it does |
|---|---|
| Camera | Multi-shot capture of up to 8 photos, shrunk to 1600 px and re-encoded on the device (which also drops GPS EXIF) before upload. Falls back to the photo library when there is no camera or no permission. |
| Ask | Type a question about two drugs on the list; the on-device guardrail — not a model — decides whether it is answered. Spoken questions are built but switched off: no model on Token Factory accepts audio, so the server reports `voice: false` and the app hides the mic. |
| Saved list | Kept on this device only (no account, no server copy). Re-checking it sends codes only — no photographs, no perception call. "Forget this list" removes it. |

Live checking of your own photographs needs the API deployed with a Nebius key.

## The problem

An elderly patient is discharged on seven prescriptions written by three specialists who never
spoke to each other, and managed at home by an adult child with no clinical training. Nobody in
that loop holds the full list, and the risk lives precisely in the gaps between prescribers.

This is tractable for one reason: **the correct answers already exist in public, authoritative,
structured data.** Tessera never asks a model to *know* medicine. Models read a label, pull the named drugs
out of label text once (offline, into a table a person reviews), and rephrase a cited passage.
Everything else is lookup.

## What it does

1. Photograph the bottles — one shot, several bottles, ordinary lighting, angled labels.
2. A vision model (MiniCPM-V 4.5) reads every label in one call: name, strength, form, directions.
3. Each drug resolves to an RxNorm ingredient `RXCUI`. When two different drugs are too close to
   call — a smudged `WARF SOD` scores warfarin and sulfacetamide within 0.039 — it **refuses to pick** and hands the
   options back. An unidentified drug carries no code, so nothing downstream can score it.
4. **Only the codes reach the reasoning service.** `["RXCUI:11289", "RXCUI:1191"]`. No image, no
   name, no date, no identifier.
5. A deterministic table resolves documented interactions; code ranks them by the label's own severity wording, and Nemotron Ultra explains each one
   and explains each one *from the cited label text*.
6. Every explanation is checked against its own citation, and the "what to do" line is held to pharmacist-referral wording by a filter. Anything the source does not support is
   dropped before you ever see it.

## Architecture

```
┌─ PERCEPTION · /api/read ───────────┐
│  photos                             │
│      ↓                              │
│  MiniCPM-V 4.5  (reads labels)      │ ──► cloud today
│      ↓                              │
│  RxNorm normalisation               │ ──► public NLM service (name leaves)
│  abstains when ambiguous or weak    │
│      ↓                              │
│  ╔═══════════════════════════════╗  │
│  ║  PRIVACY GATE                 ║  │
│  ║  allowlist: ^RXCUI:\d+$       ║  │
│  ╚═══════════════════════════════╝  │
└────────────┊───────────────────────┘
             ┊  codes only, nothing else
┌────────────┊─ REASONING (Nebius) ──┐
│  evidence retrieval over FDA labels │
│  deterministic interaction lookup   │
│  code ranks; Nemotron Ultra explains│
│  entailment check: drop unsupported │
│  names re-attached client-side after │
└─────────────────────────────────────┘
```

### The gate, three times

The codes-only boundary is enforced independently in three places, so a bug in one is not a leak:

1. **Device** — `app/src/lib/session.ts` `codeSetFor()` refuses to serialise anything that is
   not `RXCUI:<digits>`.
2. **HTTP** — `POST /api/assess` takes a request model with `extra="forbid"`. A body carrying a
   `names` field, or a drug name in `codes`, is a `422` at the boundary.
3. **Pipeline** — `src/tessera/privacy.py` `to_code_set()`, as before.

Perception (`POST /api/read`) and reasoning (`POST /api/assess`) are separate endpoints, so
the reasoning code path never receives a name. They are served by the same host today — see
[Deployment honesty](#deployment-honesty) for what that does and does not guarantee. Names are
re-joined in the browser.

The one-sentence version: **the reasoning service never learns what anyone is taking — it sees
numeric codes and returns numeric codes, and the names are re-joined on the side that already
had them.**

### Deployment honesty

The gate is real and tested, but it is not the only network boundary. Being precise about which
is which:

| Boundary | What crosses | Status |
|---|---|---|
| Browser → Tessera API `/api/read` | the photographs; the response carries the drug names back | Held in a temp directory for the one call, then deleted. Not logged. |
| Tessera API → Nebius (vision model) | the photographs | Cloud. Nemotron 3 Nano Omni, which could have run on a phone, is not served on Token Factory; on-device perception is future work. |
| Tessera API → NLM RxNorm | the OCR'd drug name as text | Public, free, no account. Could be removed by shipping a local RxNorm subset — the formulary is already committed. |
| **Browser → Tessera API `/api/assess` → Nebius (reasoning)** | **RxNorm codes only** | **Enforced and tested, three times over.** |

One more thing stated plainly: `/api/read` and `/api/assess` are two endpoints of **one**
service, called from the same browser seconds apart. The split guarantees that the reasoning
code path — and the Nebius reasoning calls — only ever receive codes. It does not stop the
operator of that one host from correlating the two requests. Running perception on the device
is what would close that, and it is the same future work as on-device perception.

Closing the first three rows is future work. Claiming they are closed today would be the "superficial"
kind of claim this project is built to avoid making.

## Why this breaks without Nemotron

A vision model reads the photographs; Nemotron does everything after them. The labels are read by
**MiniCPM-V 4.5**, an open model that is not NVIDIA's: Nemotron 3 Nano Omni was the plan, but Token
Factory does not serve it (404, and absent from the
[model catalog](https://tokenfactory.nebius.com/model-catalog.md), checked 2026-10-04). Switching
back is one line in `router.py`.

| Model | What it does | What fails without it |
|---|---|---|
| **Nemotron 3.5 Lightning** | Watch-list triage of FDA safety communications | Triage on Super instead would cost about 4–5× more per check at catalog prices ($0.06/$0.24 vs $0.30/$0.90 per million tokens). |
| **Nemotron 3 Super 120B** | The citation entailment check, and the one-off extraction of interactions from label text | Checking every explanation on the deep tier would multiply the per-session cost; without the check, unsupported sentences would reach the screen. |
| **Nemotron 3 Ultra 550B** | Plain-language explanation of each documented interaction, written only from its cited passage | Ordering does not depend on it — code ranks by the label's severity wording. Whether a smaller tier writes explanations that pass the citation check as often is exactly what the router ablation will measure; it is not measured yet. |

## How Nebius is used

- **Token Factory** — all inference, OpenAI-compatible, routed across four Nemotron tiers by a
  single module so a tier swap is one line and its cost is measurable.
- **Nemotron Lightning** — triages the formulary-wide FDA safety watcher (`src/tessera/watch.py`).
  It returns indices only; what a user reads is the FDA page's own text.
- **Spend control** — the router's per-call cost telemetry also feeds a daily USD ceiling and a
  per-caller rate limit on the public API. Hitting either degrades to the demo, with the reason
  shown.

## Measured results

`python -m evals.run_all` computes every metric below and writes
[`evals/results.md`](evals/results.md). The gold sets need hand labelling
([format](data/gold/README.md)), so **no accuracy figures are published yet, and none are
claimed.** What exists today:

| Metric | Status |
|---|---|
| Test suite | **197 Python + 91 app, passing** |
| Formulary coverage | **358** chronic-care drugs resolved to RXCUI |
| Label evidence coverage | a strict subset of the formulary — drugs we recognise but hold no label for are reported as *unchecked*, never as safe |
| RXCUI top-1 accuracy | not yet measured — needs the gold set |
| Severity precision@5 | not yet measured |
| Citation support rate | not yet measured |
| Label reading, first live call | 2 of 2 **synthetic** test labels read and normalised exactly, in one MiniCPM-V call: 2.4 s, $0.00048. Real bottle photos are next. |
| Cost per session | estimated ≈ $0.035 from catalog prices; **not yet measured end to end** |

Verified against the live RxNorm API on 2026-10-03: labels resolve to strength-level concepts
(`METF0RMIN 500 mg` → `316256`, "metformin 500 MG"), so every candidate is mapped to its
ingredient before the formulary and ambiguity checks. All seven demo labels then resolve to the
exact formulary ingredient, and the smudged `WARF SOD` puts warfarin only 0.039 ahead of
sulfacetamide, so Tessera asks instead of guessing. Known gap: some retired brand-form concepts
(e.g. "warfarin Oral Tablet [Marfarin]") return no ingredient from RxNorm and are reported as
outside the checked list. The result is incomplete, never wrong.

## What we deliberately did not build

User accounts, multi-patient support, pharmacy or insurance integration,
dose scheduling and reminders, a fine-tuned model, coverage beyond the 358-drug formulary, and
any language other than English. Each is defensible future work; none of it makes the core claim
more true.

## Safety boundary

**Tessera surfaces and cites documented information. It is not medical advice.**

It never recommends starting, stopping, or changing a dose, never diagnoses, and always routes to
a pharmacist or prescriber. Claims that their own citation does not support are *dropped*, not
flagged — a warning you cannot verify is worse than no warning, because it spends the trust that
makes the verifiable ones worth reading.

Absence of evidence is never rendered as evidence of safety. A drug outside the formulary, or one
whose label documents no interactions, is reported as such rather than silently omitted.

Questions go through a deterministic filter (`app/src/lib/guardrail.ts`) on the device before
anything else runs. Questions about changing, skipping or stopping a dose are
refused, and questions that describe an emergency are sent to emergency care. Every other
question is answered only from the already-cited risks, so no new text about drugs is generated.
A NeMo Guardrails layer is not built, and the product does not claim one. Spoken questions are
built in the app but switched off until a speech model is wired: whatever transcribes them must
return only the words, which the caregiver checks before the same filter screens them.

## Setup

```bash
git clone https://github.com/Romeo-04/tessera.git && cd tessera
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # macOS / Linux

cp .env.example .env        # add your NEBIUS_API_KEY
pytest                      # 197 tests, no credentials needed
cd app && npm install && npm test   # 91 tests
npx tsc --noEmit && npx expo lint
```

Building the evidence corpus (the first two need no API key):

```bash
python scripts/build_formulary.py      # RxNorm  -> data/formulary.csv   (committed)
python scripts/fetch_spl.py            # DailyMed -> data/spl/           (gitignored)
python scripts/build_interactions.py   # label text -> data/interactions.csv  (model-extracted: REVIEW IT)
tessera check photos/*.jpg
```

Running the product:

```bash
uvicorn tessera.api.app:create_app --factory --port 8000   # API; demo-only without a key
cd app && EXPO_PUBLIC_API_URL=http://localhost:8000 npx expo start
python scripts/build_demo.py      # regenerate the seeded demo from the corpus
python scripts/run_watch.py       # weekly: FDA safety watcher (needs TAVILY_API_KEY)
python -m evals.run_all           # every metric -> evals/results.md
```

Deploy: the web build is a static Expo export (`app/vercel.json`), so the demo never
cold-starts. Native builds go through EAS (`npx eas-cli@latest build`). The API ships as the
root `Dockerfile`. Set `EXPO_PUBLIC_API_URL` on the app build to point it at the API. Run **one**
API instance with `/app/data` on a persistent volume, because the daily spend ceiling is read
from telemetry stored there. Set `FORWARDED_ALLOW_IPS` to your platform proxy's address so the
per-caller rate limit cannot be dodged with a forged `X-Forwarded-For`.

### Deploying the API (Fly.io)

`fly.toml` is ready; nothing is deployed yet. In order:

1. Put `NEBIUS_API_KEY` in `.env`, then build the corpus locally with the commands above and
   **hand-review `data/interactions.csv`**.
2. `fly launch --no-deploy --copy-config` (keep `fly.toml`), then
   `fly volumes create tessera_data --size 1 --region sin`.
3. `fly secrets set NEBIUS_API_KEY=... TAVILY_API_KEY=...` — secrets go to Fly, never into the
   repo or the image.
4. `fly deploy`, then copy the built corpus (`data/formulary.csv`, `data/interactions.csv`,
   `data/spl/sections.jsonl`) onto the volume with `fly ssh sftp shell`, and
   `fly machine restart` so the API loads it. `/health` reports `"live": true` once it has.
5. Rebuild the app with `EXPO_PUBLIC_API_URL=https://<app>.fly.dev` and redeploy the web demo.

`build_interactions.py` prints a reminder to hand-check its output. That is not ceremony:
everything this product asserts flows from that table.

## Data sources

| Source | Used for |
|---|---|
| [RxNorm](https://www.nlm.nih.gov/research/umls/rxnorm/) (US NLM) | Drug name normalisation to `RXCUI` |
| [DailyMed](https://dailymed.nlm.nih.gov/) (US NLM) | FDA Structured Product Labels — the cited evidence |
| [openFDA](https://open.fda.gov/) (US FDA) | Not used yet |
| [Tavily](https://tavily.com/) | Search for the FDA safety-communication watcher (needs `TAVILY_API_KEY`) |

**Note on interactions.** The NLM/RxNav Drug Interaction API was **discontinued on 2 January
2024**. Tessera derives interaction assertions from the SPL *Drug Interactions* section itself,
extracted once offline and frozen to a reviewed CSV. This is better than the retired API would
have been: the assertion and the citation become the same object, rather than asserting from one
source and citing another.

## Licence

Apache-2.0. See [LICENSE](LICENSE).

Drug data is published by the U.S. National Library of Medicine and the U.S. Food and Drug
Administration and is used under their terms.
