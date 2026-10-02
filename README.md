# Tessera

**Seven bottles. One sourced list. Their data never leaves your phone.**

Tessera reads a photograph of someone's medications and returns a short, ranked list of
documented interaction risks — each one deep-linked to the FDA-approved label section it came
from. The photographs, the drug names, and the directions never leave the device. Only numeric
drug codes do.

> A Roman *tessera* was a small token you handed over **instead of** your name. That is exactly
> what the RxNorm code is here.

**Track:** Personal AI · **Built on:** Nebius Token Factory + NVIDIA Nemotron

---

## The problem

An elderly patient is discharged on seven prescriptions written by three specialists who never
spoke to each other, and managed at home by an adult child with no clinical training. Nobody in
that loop holds the full list, and the risk lives precisely in the gaps between prescribers.

This is tractable for one reason: **the correct answers already exist in public, authoritative,
structured data.** Tessera never asks a model to *know* medicine. It asks it to read a label,
normalise a name, and retrieve a documented fact. Everything else is lookup.

## What it does

1. Photograph the bottles — one shot, several bottles, ordinary lighting, angled labels.
2. **On-device** Nemotron 3 Nano Omni reads every label: name, strength, form, directions.
3. Each drug resolves to an RxNorm `RXCUI`. When two candidates are too close to call — a 500 mg
   extended-release against a 500 mg immediate-release — it asks instead of guessing.
4. **Only the codes leave the device.** `["RXCUI:11289", "RXCUI:1191"]`. No image, no name, no
   date, no identifier.
5. A deterministic table resolves documented interactions; Nemotron Ultra ranks them by severity
   and explains each one *from the cited label text*.
6. Every sentence is checked against its own citation. Anything the source does not support is
   dropped before you ever see it.

## Architecture

```
┌─ USER DEVICE ──────────────────────┐
│  photos + voice                     │
│      ↓                              │
│  Nemotron 3 Nano Omni  (OCR + ASR)  │
│      ↓                              │
│  RxNorm normalisation, with         │
│  abstention when ambiguous          │
│      ↓                              │
│  ╔═══════════════════════════════╗  │
│  ║  PRIVACY GATE                 ║  │
│  ║  allowlist: ^RXCUI:\d+$       ║  │
│  ╚═══════════════════════════════╝  │
└────────────┊───────────────────────┘
             ┊  codes only
┌────────────┊─ NEBIUS ──────────────┐
│  evidence retrieval over FDA labels │
│  deterministic interaction lookup   │
│  Nemotron Ultra: rank + explain     │
│  entailment check: drop unsupported │
└─────────────────────────────────────┘
```

The one-sentence version: **perception happens on the phone, reasoning happens on Nebius, and
the only thing that ever crosses between them is a list of numeric drug codes.**

## Why this breaks without Nemotron

| Model | What it does | What fails without it |
|---|---|---|
| **Nemotron 3 Nano Omni** | OCR of curved bottle labels, multi-image reasoning in one unified context, native speech for the spoken question | On-device perception becomes impossible. We would need separate vision and speech vendors, the images would have to leave the device to reach them, and the privacy split — the entire product — collapses. |
| **Nemotron 3.5 Lightning** | High-volume cheap passes: candidate shortlisting, watch-list triage | The always-on watch becomes ~15× more expensive per check and gets cut. |
| **Nemotron 3 Super 120B** | Native function calling to RxNorm and DailyMed; the citation entailment check | Tool orchestration degrades to brittle hand-parsed calls, and per-claim verification becomes too expensive to run on every sentence. |
| **Nemotron 3 Ultra 550B** | Severity adjudication and plain-language explanation from retrieved evidence | Ranking collapses to the raw severity grade, and alert fatigue — the documented failure mode of every interaction checker — returns. |

## How Nebius is used

- **Token Factory** — all inference, OpenAI-compatible, routed across four Nemotron tiers by a
  single module so a tier swap is one line and its cost is measurable.
- **Qwen3-Embedding-8B** — retrieval over FDA label spans.
- **Token Factory Sandboxes** *(Plan 2)* — the deterministic resolver runs isolated and auditable.
- **Nebius AI Cloud** *(Plan 2)* — one-time corpus embedding and the evaluation harness.

## Measured results

The evaluation harness and gold sets are Plan 2. **No accuracy figures are published here yet,
and none are claimed.** What exists today:

| Metric | Status |
|---|---|
| Test suite | **84 passing** |
| Formulary coverage | **358** chronic-care drugs resolved to RXCUI |
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

## Setup

```bash
git clone https://github.com/Romeo-04/tessera.git && cd tessera
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # macOS / Linux

cp .env.example .env        # add your NEBIUS_API_KEY
pytest                      # 84 tests, no credentials needed
```

Building the evidence corpus (the first two need no API key):

```bash
python scripts/build_formulary.py      # RxNorm  -> data/formulary.csv   (committed)
python scripts/fetch_spl.py            # DailyMed -> data/spl/           (gitignored)
python scripts/build_interactions.py   # label text -> data/interactions.csv  (REVIEW IT)
python scripts/build_index.py          # embeddings -> data/index/       (gitignored)
tessera check photos/*.jpg
```

`build_interactions.py` prints a reminder to hand-check its output. That is not ceremony:
everything this product asserts flows from that table.

## Data sources

| Source | Used for |
|---|---|
| [RxNorm](https://www.nlm.nih.gov/research/umls/rxnorm/) (US NLM) | Drug name normalisation to `RXCUI` |
| [DailyMed](https://dailymed.nlm.nih.gov/) (US NLM) | FDA Structured Product Labels — the cited evidence |
| [openFDA](https://open.fda.gov/) (US FDA) | Recalls and adverse event reports *(Plan 2)* |

**Note on interactions.** The NLM/RxNav Drug Interaction API was **discontinued on 2 January
2024**. Tessera derives interaction assertions from the SPL *Drug Interactions* section itself,
extracted once offline and frozen to a reviewed CSV. This is better than the retired API would
have been: the assertion and the citation become the same object, rather than asserting from one
source and citing another.

## Licence

Apache-2.0. See [LICENSE](LICENSE).

Drug data is published by the U.S. National Library of Medicine and the U.S. Food and Drug
Administration and is used under their terms.
