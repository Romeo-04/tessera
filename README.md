# Tessera

**Seven bottles. One sourced list. Every claim traceable to an FDA label.**

Tessera reads a photograph of someone's medications and returns a short, ranked list of
documented interaction risks — each one linked to the FDA-approved label section it came from.

**What the privacy gate actually guarantees today:** the reasoning service — retrieval,
interaction resolution, severity adjudication — receives *only* numeric RxNorm codes. No drug
names, strengths, directions, dates, or images reach it. That boundary is enforced in code
(`src/tessera/privacy.py`) and tested on the serialised payload, not just the object.

**What it does not yet guarantee, stated plainly:** perception currently runs in the cloud, not
on the device. Two things cross a network *above* that gate — the photographs go to Nebius for
Omni to read, and the OCR'd drug name goes to the NLM's public RxNorm service to be normalised.
An on-device Omni build is the intended end state and is not implemented. See
[Deployment honesty](#deployment-honesty).

> A Roman *tessera* was a small token you handed over **instead of** your name. That is exactly
> what the RxNorm code is here.

**Track:** Personal AI · **Built on:** Nebius Token Factory + NVIDIA Nemotron

---

## Try it

The web app opens on a **seeded demo**: seven real medications, real FDA label text, the real
resolver and five-risk cap. It needs no camera, no upload, no account and no credentials, and
it makes no model calls. Live checking of your own photographs is available when the API is
deployed with a Nebius key.

```bash
cd web && npm install && npm run dev      # http://localhost:5173
```

The right-hand panel shows the exact JSON the browser sends across the privacy gate.

## The problem

An elderly patient is discharged on seven prescriptions written by three specialists who never
spoke to each other, and managed at home by an adult child with no clinical training. Nobody in
that loop holds the full list, and the risk lives precisely in the gaps between prescribers.

This is tractable for one reason: **the correct answers already exist in public, authoritative,
structured data.** Tessera never asks a model to *know* medicine. It asks it to read a label,
normalise a name, and retrieve a documented fact. Everything else is lookup.

## What it does

1. Photograph the bottles — one shot, several bottles, ordinary lighting, angled labels.
2. Nemotron 3 Nano Omni reads every label in one call: name, strength, form, directions.
3. Each drug resolves to an RxNorm `RXCUI`. When two candidates are too close to call — a 500 mg
   extended-release against a 500 mg immediate-release — it **refuses to pick** and hands the
   options back. An unidentified drug carries no code, so nothing downstream can score it.
4. **Only the codes reach the reasoning service.** `["RXCUI:11289", "RXCUI:1191"]`. No image, no
   name, no date, no identifier.
5. A deterministic table resolves documented interactions; Nemotron Ultra ranks them by severity
   and explains each one *from the cited label text*.
6. Every sentence is checked against its own citation. Anything the source does not support is
   dropped before you ever see it.

## Architecture

```
┌─ CLIENT ───────────────────────────┐
│  photos + voice                     │
│      ↓                              │
│  Nemotron 3 Nano Omni  (OCR + ASR)  │ ──► cloud today, on-device intended
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
│  Nemotron Ultra: rank + explain     │
│  entailment check: drop unsupported │
│  names re-attached client-side after │
└─────────────────────────────────────┘
```

### The gate, three times

The codes-only boundary is enforced independently in three places, so a bug in one is not a leak:

1. **Browser** — `web/src/lib/session.ts` `codeSetFor()` refuses to serialise anything that is
   not `RXCUI:<digits>`.
2. **HTTP** — `POST /api/assess` takes a request model with `extra="forbid"`. A body carrying a
   `names` field, or a drug name in `codes`, is a `422` at the boundary.
3. **Pipeline** — `src/tessera/privacy.py` `to_code_set()`, as before.

Perception (`POST /api/read`) and reasoning (`POST /api/assess`) are separate endpoints, so
the split the diagram shows is the split the code has. Names are re-joined in the browser.

The one-sentence version: **the reasoning service never learns what anyone is taking — it sees
numeric codes and returns numeric codes, and the names are re-joined on the side that already
had them.**

### Deployment honesty

The gate is real and tested, but it is not the only network boundary. Being precise about which
is which:

| Boundary | What crosses | Status |
|---|---|---|
| Client → Nebius (Omni) | the photographs | Cloud today. On-device Omni is the intended end state; Omni needs ~25 GB and a quantised build is not done. |
| Client → NLM RxNorm | the OCR'd drug name as text | Public, free, no account. Could be removed by shipping a local RxNorm subset — the formulary is already committed. |
| **Client → Nebius (reasoning)** | **RxNorm codes only** | **Enforced and tested.** |

Closing the first two is future work. Claiming they are closed today would be the "superficial"
kind of claim this project is built to avoid making.

## Why this breaks without Nemotron

| Model | What it does | What fails without it |
|---|---|---|
| **Nemotron 3 Nano Omni** | OCR of curved bottle labels, multi-image reasoning in one unified context, native speech for the spoken question | We would need separate vision and speech vendors, each seeing the raw images, and the on-device end state would become unreachable — no other open model does all three modalities in one 30B/3B-active package. |
| **Nemotron 3.5 Lightning** | High-volume cheap passes: candidate shortlisting, watch-list triage | The always-on watch becomes ~15× more expensive per check and gets cut. |
| **Nemotron 3 Super 120B** | Native function calling to RxNorm and DailyMed; the citation entailment check | Tool orchestration degrades to brittle hand-parsed calls, and per-claim verification becomes too expensive to run on every sentence. |
| **Nemotron 3 Ultra 550B** | Severity adjudication and plain-language explanation from retrieved evidence | Ranking collapses to the raw severity grade, and alert fatigue — the documented failure mode of every interaction checker — returns. |

## How Nebius is used

- **Token Factory** — all inference, OpenAI-compatible, routed across four Nemotron tiers by a
  single module so a tier swap is one line and its cost is measurable.
- **Qwen3-Embedding-8B** — retrieval over FDA label spans.
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
| Test suite | **169 Python + 41 web, passing** |
| Formulary coverage | **358** chronic-care drugs resolved to RXCUI |
| Label evidence coverage | a strict subset of the formulary — drugs we recognise but hold no label for are reported as *unchecked*, never as safe |
| RXCUI top-1 accuracy | not yet measured — needs the gold set |
| Severity precision@5 | not yet measured |
| Citation support rate | not yet measured |
| Cost per session | estimated ≈ $0.035; **not yet confirmed against live pricing** |

The one number already verified against the live API is normalisation separation: `METF0RMIN 500`
(OCR digit-zero) resolves to the correct concept with a 0.055 margin over the runner-up, while
`WARFARIN SODIUM 5MG` separates by only 0.037 and is therefore sent back for human confirmation.

## What we deliberately did not build

User accounts, multi-patient support, a native mobile app, pharmacy or insurance integration,
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

Typed questions go through a deterministic filter (`web/src/lib/guardrail.ts`) before
anything else runs. Questions about changing, skipping or stopping a dose are refused, and
questions that describe an emergency are sent to emergency care. Every other question is
answered only from the already-cited risks, so no new text about drugs is generated. Spoken
questions through Omni's audio pathway and a NeMo Guardrails layer are not built, and the
product does not claim them.

## Setup

```bash
git clone https://github.com/Romeo-04/tessera.git && cd tessera
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # macOS / Linux

cp .env.example .env        # add your NEBIUS_API_KEY
pytest                      # 169 tests, no credentials needed
cd web && npm install && npm test   # 41 tests
```

Building the evidence corpus (the first two need no API key):

```bash
python scripts/build_formulary.py      # RxNorm  -> data/formulary.csv   (committed)
python scripts/fetch_spl.py            # DailyMed -> data/spl/           (gitignored)
python scripts/build_interactions.py   # label text -> data/interactions.csv  (REVIEW IT)
python scripts/build_index.py          # embeddings -> data/index/       (gitignored)
tessera check photos/*.jpg
```

Running the product:

```bash
uvicorn tessera.api.app:create_app --factory --port 8000   # API; demo-only without a key
cd web && npm run dev                                        # proxies /api to :8000
python scripts/build_demo.py      # regenerate the seeded demo from the corpus
python scripts/run_watch.py       # weekly: FDA safety watcher (needs TAVILY_API_KEY)
python -m evals.run_all           # every metric -> evals/results.md
```

Deploy: `web/` is static (`web/vercel.json`), so the demo never cold-starts. The API ships as
the root `Dockerfile`. Set `VITE_API_URL` on the web build to point it at the API.

`build_interactions.py` prints a reminder to hand-check its output. That is not ceremony:
everything this product asserts flows from that table.

## Data sources

| Source | Used for |
|---|---|
| [RxNorm](https://www.nlm.nih.gov/research/umls/rxnorm/) (US NLM) | Drug name normalisation to `RXCUI` |
| [DailyMed](https://dailymed.nlm.nih.gov/) (US NLM) | FDA Structured Product Labels — the cited evidence |
| [openFDA](https://open.fda.gov/) (US FDA) | Not used yet |

**Note on interactions.** The NLM/RxNav Drug Interaction API was **discontinued on 2 January
2024**. Tessera derives interaction assertions from the SPL *Drug Interactions* section itself,
extracted once offline and frozen to a reviewed CSV. This is better than the retired API would
have been: the assertion and the citation become the same object, rather than asserting from one
source and citing another.

## Licence

Apache-2.0. See [LICENSE](LICENSE).

Drug data is published by the U.S. National Library of Medicine and the U.S. Food and Drug
Administration and is used under their terms.
