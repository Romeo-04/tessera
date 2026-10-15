"""Drug classes as FDA labels write them, mapped to the formulary drugs they cover.

Labels often warn about a class ("ACE inhibitors", "antidiabetic medicines")
rather than naming each drug. This map turns the class phrase a label uses into
the classes it means. It is deliberately small, written by hand and reviewable:
label wording does not follow NLM's taxonomy (spironolactone is the textbook
"potassium-sparing diuretic", but RxClass files it under "Aldosterone
Antagonist"), so a blind name lookup would be wrong.

A wrong expansion puts a false warning in a safety table, so every rule here
errs toward claiming less:

- A phrase may name several classes ("ACE inhibitors and ARBs"); all of them
  count. An entry that `refines` a broader one ("loop diuretics" refines
  "diuretics") suppresses it where its match contains the broader match, so
  "loop diuretics" is not read as every diuretic, while "thiazides and other
  diuretics" still is both.
- A phrase that names only part of a class ("certain phenothiazines", "select
  protease inhibitors", "intravenous beta-blockers") expands to nothing: the
  label lists which ones elsewhere, and guessing would over-claim.
- "other than X", "but not X", "except X" remove X (see `excluded_text`).

Each entry lists its members one way: `rxclass`, items of (class name exactly
as RxClass spells it, class type), or `ingredients`, names written out where
RxClass is wrong for the purpose. `exclude` removes ingredients RxClass files in
a class but a label's wording does not mean. scripts/build_class_members.py
resolves all of it to formulary codes and fails loudly on an unknown class.
"""
from __future__ import annotations

import re

_CYP = r"CYP\s?3A4?"
# "Strong CYP2D6 and CYP3A4 inhibitors": another enzyme may sit between.
_CYP_ANY = rf"(CYP\s?\w+\s+(and|or)\s+)?{_CYP}"
_STRONG = r"(strong|potent)"
_BOTH = r"((strong|potent)\s+(and|or|and/or)\s+moderate|moderate\s+(and|or|and/or)\s+(strong|potent))"

_STRONG_INHIBITORS = ["clarithromycin", "itraconazole", "ketoconazole", "posaconazole",
                      "voriconazole", "ritonavir", "cobicistat", "nefazodone", "nelfinavir",
                      "telithromycin"]
_MODERATE_INHIBITORS = ["aprepitant", "ciprofloxacin", "cyclosporine", "diltiazem",
                        "dronedarone", "erythromycin", "fluconazole", "fluvoxamine",
                        "imatinib", "verapamil"]
_STRONG_INDUCERS = ["apalutamide", "carbamazepine", "enzalutamide", "mitotane", "phenytoin",
                    "rifampin"]
_MODERATE_INDUCERS = ["bosentan", "efavirenz", "etravirine", "phenobarbital", "primidone"]


def _cyp(kind: str) -> list[dict]:
    """Strong / moderate / either / unqualified entries for CYP3A4 `kind`
    ("inhibitor" or "inducer"). The FDA's "Table of Substrates, Inhibitors and
    Inducers" is used instead of RxClass, which ignores strength, lists
    substrates such as ticagrelor as inhibitors, and misses rifampin and
    phenytoin as inducers. The label's own word picks the list."""
    strong, moderate = ((_STRONG_INHIBITORS, _MODERATE_INHIBITORS) if kind == "inhibitor"
                        else (_STRONG_INDUCERS, _MODERATE_INDUCERS))
    k = f"{kind}s?"
    general = f"cyp3a4-{kind}s"

    def forms(word: str) -> list[str]:
        return [rf"{word}\s+{_CYP_ANY}\s+{k}", rf"{word}\s+{k}\s+of\s+{_CYP}"]

    return [
        {"key": f"cyp3a4-strong-or-moderate-{kind}s", "patterns": forms(_BOTH),
         "ingredients": strong + moderate,
         "refines": [general, f"cyp3a4-strong-{kind}s", f"cyp3a4-moderate-{kind}s"]},
        {"key": f"cyp3a4-strong-{kind}s", "patterns": forms(_STRONG),
         "ingredients": strong, "refines": [general]},
        {"key": f"cyp3a4-moderate-{kind}s", "patterns": forms("moderate"),
         "ingredients": moderate, "refines": [general]},
        {"key": general,
         "patterns": [rf"{_CYP}\s+{k}", rf"{k}\s+of\s+{_CYP}",
                      # "CYP3A4 inducers and inhibitors" names both kinds.
                      rf"{_CYP}\s+(inducers?|inhibitors?)\s+and\s+{k}"],
         "ingredients": strong + moderate},
    ]


_DIURETIC_MEMBERS = [("Thiazide Diuretic", "EPC"), ("Thiazide-like Diuretic", "EPC"),
                     ("Loop Diuretic", "EPC")]

CLASS_MAP: list[dict] = [
    {"key": "ace-inhibitors",
     "patterns": [r"\bACE\s+inhibitor", r"angiotensin[- ]converting[- ]enzyme(\s*\(ACE\))?\s+inhibitors?"],
     "rxclass": [("Angiotensin Converting Enzyme Inhibitor", "EPC")]},
    {"key": "arbs",
     "patterns": [r"angiotensin\s+(II\s+)?receptor\s+(blockers?|blocking|antagonists?)", r"\bARBs?\b"],
     "rxclass": [("Angiotensin 2 Receptor Blocker", "EPC")]},
    {"key": "ras-inhibitors",
     "patterns": [r"\bRAS\b", r"renin[- ]angiotensin"],
     "rxclass": [("Angiotensin Converting Enzyme Inhibitor", "EPC"),
                 ("Angiotensin 2 Receptor Blocker", "EPC"), ("Renin Inhibitor", "EPC")]},
    # "Non-potassium-sparing diuretics" means the opposite set: loop and thiazide.
    {"key": "potassium-depleting-diuretics",
     "patterns": [r"non-?\s?potassium[- ]sparing\s+diuretics?", r"potassium[- ]depleting\s+diuretics?"],
     "rxclass": _DIURETIC_MEMBERS,
     "refines": ["potassium-sparing-diuretics", "diuretics"]},
    {"key": "potassium-sparing-diuretics",
     "patterns": [r"potassium[- ]sparing\s+diuretics?"],
     "rxclass": [("Potassium-sparing Diuretic", "EPC"), ("Aldosterone Antagonist", "EPC")],
     "refines": ["diuretics"]},
    {"key": "thiazide-diuretics",
     "patterns": [r"thiazide(-type|-like|\s+type)?\s+diuretics?", r"\bthiazides?\b"],
     "rxclass": [("Thiazide Diuretic", "EPC"), ("Thiazide-like Diuretic", "EPC")],
     "refines": ["diuretics"]},
    {"key": "loop-diuretics",
     "patterns": [r"loop\s+diuretics?"],
     "rxclass": [("Loop Diuretic", "EPC")],
     "refines": ["diuretics"]},
    {"key": "diuretics",
     "patterns": [r"\bdiuretics?\b"],
     "rxclass": _DIURETIC_MEMBERS + [("Potassium-sparing Diuretic", "EPC"),
                                     ("Aldosterone Antagonist", "EPC")]},
    {"key": "sulfonylureas",
     "patterns": [r"sulfonylureas?"],
     "rxclass": [("Sulfonylurea", "EPC")]},
    {"key": "insulin-secretagogues",
     "patterns": [r"insulin\s+secretagogues?"],
     "ingredients": ["glimepiride", "glipizide", "glyburide", "repaglinide", "nateglinide"]},
    {"key": "insulins",
     # Not "non-insulin", "insulin sensitizers", "insulin resistance".
     "patterns": [r"(?<!non-)(?<!non )\binsulins?\b(?!\s+(secretagogue|sensiti|resistan))"],
     "rxclass": [("Insulin", "EPC")]},
    {"key": "antidiabetics",
     # Not "blood glucose lowering": "drugs that may decrease the blood glucose
     # lowering effect of repaglinide" are not antidiabetics.
     "patterns": [r"anti-?diabetic", r"hypoglycemic\s+agents?"],
     "rxclass": [("Sulfonylurea", "EPC"), ("Biguanide", "EPC"), ("Dipeptidyl Peptidase 4 Inhibitor", "EPC"),
                 ("Sodium-Glucose Cotransporter 2 Inhibitor", "EPC"), ("Thiazolidinedione", "EPC"),
                 ("Insulin", "EPC")]},
    {"key": "fenamates",
     "patterns": [r".*\bfenamates?\b"],
     "ingredients": ["mefenamic acid", "meclofenamate"],
     "refines": ["nsaids"]},
    {"key": "nsaids",
     "patterns": [r"\bNSAIDs?\b", r"non-?\s?steroidal\s+anti-?\s?inflammatory"],
     "rxclass": [("Nonsteroidal Anti-inflammatory Drug", "EPC")]},
    {"key": "cox2-inhibitors",
     "patterns": [r"COX-?2\s+inhibitors?", r"cyclooxygenase-?2\s+inhibitors?"],
     "ingredients": ["celecoxib"]},
    {"key": "salicylates",
     "patterns": [r"\bsalicylates?\b"],
     "ingredients": ["aspirin", "salsalate"]},
    {"key": "coumarins",
     "patterns": [r"coumarins?", r"coumarin[- ]type\s+anticoagulants?"],
     "ingredients": ["warfarin"]},
    {"key": "digitalis",
     "patterns": [r"digitalis", r"cardiac\s+glycosides?"],
     "ingredients": ["digoxin"]},
    {"key": "thyroid",
     "patterns": [r"\bthyroid\s+(products?|hormones?|preparations?|replacement)"],
     "ingredients": ["levothyroxine", "liothyronine"]},
    {"key": "carbonic-anhydrase-inhibitors",
     # The metformin label's own list: topiramate, zonisamide, acetazolamide,
     # dichlorphenamide. RxClass's class adds eye drops.
     "patterns": [r"carbonic\s+anhydrase\s+inhibitors?"],
     "ingredients": ["acetazolamide", "dichlorphenamide", "methazolamide", "topiramate", "zonisamide"]},
    {"key": "fibrates",
     "patterns": [r"\bfibrates?\b", r"fibric\s+acid\s+derivatives?"],
     "ingredients": ["fenofibrate", "fenofibric acid", "gemfibrozil"]},
    {"key": "tricyclics",
     "patterns": [r"tricyclic\s+antidepressants?", r"\btricyclics\b", r"\bTCAs?\b"],
     "rxclass": [("Tricyclic Antidepressant", "EPC")]},
    {"key": "phenothiazines",
     "patterns": [r"phenothiazines?"],
     "rxclass": [("Phenothiazine", "EPC")]},
    {"key": "atypical-antipsychotics",
     "patterns": [r"atypical\s+antipsychotics?"],
     "rxclass": [("Atypical Antipsychotic", "EPC")]},
    {"key": "barbiturates",
     "patterns": [r"barbiturates?"],
     "ingredients": ["butalbital", "phenobarbital", "primidone"]},  # DailyMed gives phenobarbital no EPC
    {"key": "quinolones",
     "patterns": [r"(fluoro)?quinolones?"],
     "rxclass": [("Fluoroquinolone Antibacterial", "EPC")]},
    {"key": "macrolides",
     "patterns": [r"\bmacrolides?\b"],
     "ingredients": ["azithromycin", "clarithromycin", "erythromycin"]},
    {"key": "azole-antifungals",
     "patterns": [r"azole\s+antifungals?"],
     "rxclass": [("Azole Antifungal", "EPC")]},
    {"key": "hiv-protease-inhibitors",
     "patterns": [r"^(?!.*(HCV|hepatitis|neprilysin)).*\bprotease\s+inhibitors?"],
     # RxClass's "Protease Inhibitor" EPC also holds DPP-4 and ACE inhibitors.
     "ingredients": ["atazanavir", "darunavir", "fosamprenavir", "indinavir", "lopinavir",
                     "nelfinavir", "ritonavir", "saquinavir", "tipranavir"]},
    {"key": "statins",
     "patterns": [r"\bstatins?\b", r"HMG-?CoA\s+reductase\s+inhibitors?"],
     "rxclass": [("HMG-CoA Reductase Inhibitor", "EPC")]},
    {"key": "cardioselective-beta-blockers",
     "patterns": [r"cardioselective\s+beta[- ](adrenergic\s+)?block\w*"],
     "ingredients": ["acebutolol", "atenolol", "betaxolol", "bisoprolol", "metoprolol", "nebivolol"],
     "refines": ["beta-blockers"]},
    {"key": "beta-blockers",
     "patterns": [r"beta[- ](adrenergic\s+)?block(ers?|ing\s+agents?)"],
     "rxclass": [("beta-Adrenergic Blocker", "EPC")]},
    {"key": "dihydropyridine-ccbs",
     "patterns": [r"dihydropyridine\s+calcium\s+channel\s+block\w*"],
     "ingredients": ["amlodipine", "felodipine", "isradipine", "nicardipine", "nifedipine", "nisoldipine"],
     "refines": ["calcium-channel-blockers"]},
    {"key": "non-dihydropyridine-ccbs",
     "patterns": [r"(verapamil|diltiazem)-?\s+(or\s+(verapamil|diltiazem)-?\s*)?type\s+calcium\s+channel\s+block\w*",
                  r"calcium\s+channel\s+block\w*\s+of\s+the\s+(verapamil|diltiazem)(\s+or\s+(verapamil|diltiazem))?\s+type",
                  r"non-?\s?dihydropyridine\s+calcium\s+channel\s+block\w*"],
     "ingredients": ["diltiazem", "verapamil"],
     "refines": ["calcium-channel-blockers"]},
    {"key": "calcium-channel-blockers",
     "patterns": [r"calcium\s+channel\s+block(ers?|ing)"],
     "rxclass": [("Calcium Channel Blocker", "EPC")]},
    {"key": "ssris",
     "patterns": [r"\bSSRIs?\b", r"selective\s+serotonin\s+(and\s+serotonin\s+norepinephrine\s+)?reuptake\s+inhibitors?"],
     "rxclass": [("Serotonin Reuptake Inhibitor", "EPC")],
     "exclude": ["trazodone"]},  # an SARI, not what a label means by "SSRIs"
    {"key": "snris",
     "patterns": [r"\bSNRIs?\b", r"serotonin[- ](and\s+)?norepinephrine\s+reuptake\s+inhibitors?"],
     "rxclass": [("Serotonin and Norepinephrine Reuptake Inhibitor", "EPC")]},
    {"key": "maois",
     "patterns": [r"\bMAOIs?\b", r"monoamine\s+oxidase\s+inhibitors?"],
     "rxclass": [("Monoamine Oxidase Inhibitor", "EPC")]},
    {"key": "partial-agonist-opioids",
     "patterns": [r"(mixed\s+agonist|partial\s+agonist).*opioid\w*"],
     "ingredients": ["buprenorphine", "butorphanol", "nalbuphine", "pentazocine"],
     "refines": ["opioids"]},
    {"key": "opioids",
     "patterns": [r"(?<!non-)(?<!non )\bopioids?\b"],
     "rxclass": [("Opioid Agonist", "EPC")],
     "exclude": ["loperamide"]},  # gut-acting; not what an opioid CNS warning means
    {"key": "benzodiazepines",
     "patterns": [r"benzodiazepines?"],
     "rxclass": [("Benzodiazepine", "EPC")]},
    *_cyp("inhibitor"),
    *_cyp("inducer"),
]

# Words that make a phrase name only part of a class. The label names the
# members it means elsewhere; expanding to the whole class would over-claim.
# "Weak" CYP3A4 inhibitors are on neither the strong nor the moderate list.
_SUBSET = re.compile(r"\b(certain|select|selected|some|specific|intravenous|IV|weak|mild)\b",
                     re.IGNORECASE)
_EXCLUSION = re.compile(r"\b(other\s+than|but\s+not|except(\s+for)?|excluding)\b(?P<rest>.*)",
                        re.IGNORECASE)
_HYPHENS = re.compile(r"[­‐‑‒–—―−]")
_ALIASES = [(re.compile(r"acetyl\s?salicylic\s+acid", re.IGNORECASE), "aspirin")]

_COMPILED = [(e["key"], [re.compile(p, re.IGNORECASE) for p in e["patterns"]], set(e.get("refines", [])))
             for e in CLASS_MAP]


def normalize_phrase(phrase: str) -> str:
    """Typographic hyphens to "-", known synonyms to the formulary name."""
    out = _HYPHENS.sub("-", phrase or "")
    for pattern, name in _ALIASES:
        out = pattern.sub(name, out)
    return out


# The model extracts a phrase, but sometimes the label qualifies it just before:
# corticosteroid labels warn about "potassium-depleting agents (e.g., amphotericin
# B, diuretics)", and "diuretics" there excludes the potassium-sparing ones.
# (key, cue in the text just before the phrase, key to read it as instead)
_CONTEXT = [("diuretics", re.compile(r"potassium[- ]depleting", re.IGNORECASE),
             "potassium-depleting-diuretics")]
_CONTEXT_WINDOW = 150


def match_classes(phrase: str, context: str = "") -> list[str]:
    """Every class key a label's class phrase refers to, in map order.

    Empty for an unmapped phrase, and for one that names only part of a class.
    The exclusion clause ("other than gemfibrozil") is not searched for classes.
    `context`, the cited passage, lets a qualifier just before the phrase
    narrow it (see _CONTEXT).
    """
    keys = _match(phrase)
    text = normalize_phrase(context)
    hit = re.search(re.escape(normalize_phrase(phrase).strip()), text, re.IGNORECASE) if context else None
    if hit:
        # Only the phrase's own sentence: a cue in the sentence before is about
        # something else, and reading it would drop real members.
        before = text[max(0, hit.start() - _CONTEXT_WINDOW):hit.start()]
        before = re.split(r"[.;]\s", before)[-1]
        for key, cue, instead in _CONTEXT:
            if key in keys and cue.search(before):
                keys = [instead if k == key else k for k in keys]
    return keys


def _match(phrase: str) -> list[str]:
    text = normalize_phrase(phrase)
    if not text.strip() or _SUBSET.search(text):
        return []
    m = _EXCLUSION.search(text)
    if m:
        text = text[:m.start()]
    spans: dict[str, list[tuple[int, int]]] = {}
    for key, patterns, _ in _COMPILED:
        for p in patterns:
            spans.setdefault(key, []).extend(x.span() for x in p.finditer(text))
        if not spans[key]:
            del spans[key]
    suppressed = set()
    for key, _, refines in _COMPILED:
        for parent in refines & spans.keys() if key in spans else ():
            if all(any(s <= ps and pe <= e for s, e in spans[key]) for ps, pe in spans[parent]):
                suppressed.add(parent)
    return [key for key, _, _ in _COMPILED if key in spans and key not in suppressed]


def excluded_text(phrase: str) -> str:
    """The part of a phrase after "other than" / "but not" / "except", lowercased:
    any formulary drug named in it is left out of the expansion."""
    m = _EXCLUSION.search(normalize_phrase(phrase))
    return m.group("rest").lower() if m else ""
