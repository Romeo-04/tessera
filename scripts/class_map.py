"""Drug classes as FDA labels write them, mapped to NLM RxClass classes.

Labels often warn about a class ("ACE inhibitors", "antidiabetic medicines")
rather than naming each drug. This map turns the class phrase a label uses into
the RxClass classes whose members it covers. It is deliberately small, written
by hand and reviewable: label wording does not follow NLM's taxonomy
(spironolactone is the textbook "potassium-sparing diuretic", but RxClass files
it under "Aldosterone Antagonist"), so a blind name lookup would be wrong.

Order matters: the first matching entry wins, so specific classes come before
the general ones that would also match ("thiazide diuretics" before
"diuretics"; "strong CYP3A4 inhibitors" before "CYP3A4 inhibitors").

An entry lists its members one way: `rxclass`, items of (class name exactly
as RxClass spells it, class type), or `ingredients`, names written out where
RxClass is wrong for the purpose. `exclude` removes ingredients RxClass files in
a class but a label's wording does not mean. scripts/build_class_members.py
resolves all of it to formulary codes and fails loudly on an unknown class.
"""
from __future__ import annotations

import re

_CYP = r"CYP\s?3A4?"
_STRONG_INHIBITORS = ["clarithromycin", "itraconazole", "ketoconazole", "posaconazole",
                      "voriconazole", "ritonavir", "cobicistat", "nefazodone", "nelfinavir",
                      "telithromycin"]
_MODERATE_INHIBITORS = ["aprepitant", "ciprofloxacin", "cyclosporine", "diltiazem",
                        "dronedarone", "erythromycin", "fluconazole", "fluvoxamine",
                        "imatinib", "verapamil"]
_STRONG_INDUCERS = ["apalutamide", "carbamazepine", "enzalutamide", "mitotane", "phenytoin",
                    "rifampin"]
_MODERATE_INDUCERS = ["bosentan", "efavirenz", "etravirine", "phenobarbital", "primidone"]

CLASS_MAP: list[dict] = [
    {"key": "ace-inhibitors",
     "patterns": [r"\bACE\s+inhibitors?\b", r"angiotensin[- ]converting[- ]enzyme(\s*\(ACE\))?\s+inhibitors?"],
     "rxclass": [("Angiotensin Converting Enzyme Inhibitor", "EPC")]},
    {"key": "arbs",
     "patterns": [r"angiotensin\s+(II\s+)?receptor\s+(blockers?|blocking|antagonists?)", r"\bARBs?\b"],
     "rxclass": [("Angiotensin 2 Receptor Blocker", "EPC")]},
    {"key": "ras-inhibitors",
     "patterns": [r"\bRAS\b", r"renin[- ]angiotensin"],
     "rxclass": [("Angiotensin Converting Enzyme Inhibitor", "EPC"),
                 ("Angiotensin 2 Receptor Blocker", "EPC"), ("Renin Inhibitor", "EPC")]},
    {"key": "potassium-sparing-diuretics",
     "patterns": [r"potassium[- ]sparing\s+diuretics?"],
     "rxclass": [("Potassium-sparing Diuretic", "EPC"), ("Aldosterone Antagonist", "EPC")]},
    {"key": "thiazide-diuretics",
     "patterns": [r"thiazide(-type|-like|\s+type)?\s+diuretics?", r"\bthiazides?\b"],
     "rxclass": [("Thiazide Diuretic", "EPC"), ("Thiazide-like Diuretic", "EPC")]},
    {"key": "loop-diuretics",
     "patterns": [r"loop\s+diuretics?"],
     "rxclass": [("Loop Diuretic", "EPC")]},
    {"key": "diuretics",
     "patterns": [r"\bdiuretics?\b"],
     "rxclass": [("Thiazide Diuretic", "EPC"), ("Thiazide-like Diuretic", "EPC"), ("Loop Diuretic", "EPC"),
                 ("Potassium-sparing Diuretic", "EPC"), ("Aldosterone Antagonist", "EPC")]},
    {"key": "sulfonylureas",
     "patterns": [r"sulfonylureas?"],
     "rxclass": [("Sulfonylurea", "EPC")]},
    {"key": "insulin-secretagogues",
     "patterns": [r"insulin\s+secretagogues?"],
     "ingredients": ["glimepiride", "glipizide", "glyburide", "repaglinide", "nateglinide"]},
    {"key": "insulins",
     "patterns": [r"^\s*insulins?\s*$"],
     "rxclass": [("Insulin", "EPC")]},
    {"key": "antidiabetics",
     "patterns": [r"anti-?diabetic", r"hypoglycemic\s+agents?", r"blood[- ]glucose[- ]lowering"],
     "rxclass": [("Sulfonylurea", "EPC"), ("Biguanide", "EPC"), ("Dipeptidyl Peptidase 4 Inhibitor", "EPC"),
                 ("Sodium-Glucose Cotransporter 2 Inhibitor", "EPC"), ("Thiazolidinedione", "EPC"),
                 ("Insulin", "EPC")]},
    {"key": "nsaids",
     "patterns": [r"\bNSAIDs?\b", r"non-?\s?steroidal\s+anti-?\s?inflammatory"],
     "rxclass": [("Nonsteroidal Anti-inflammatory Drug", "EPC")]},
    # After NSAIDs: "NSAIDs including selective COX-2 inhibitors" means all NSAIDs.
    {"key": "cox2-inhibitors",
     "patterns": [r"COX-?2\s+inhibitors?", r"cyclooxygenase-?2\s+inhibitors?"],
     "ingredients": ["celecoxib"]},
    {"key": "salicylates",
     "patterns": [r"salicylates?"],
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
     "patterns": [r"tricyclic\s+antidepressants?", r"\bTCAs?\b"],
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
    {"key": "azole-antifungals",
     "patterns": [r"azole\s+antifungals?"],
     "rxclass": [("Azole Antifungal", "EPC")]},
    {"key": "hiv-protease-inhibitors",
     "patterns": [r"(?<!neprilysin\s)\bprotease\s+inhibitors?"],
     # RxClass's "Protease Inhibitor" EPC also holds DPP-4 and ACE inhibitors.
     "ingredients": ["atazanavir", "darunavir", "fosamprenavir", "indinavir", "lopinavir",
                     "nelfinavir", "ritonavir", "saquinavir", "tipranavir"]},
    {"key": "statins",
     "patterns": [r"\bstatins?\b", r"HMG-?CoA\s+reductase\s+inhibitors?"],
     "rxclass": [("HMG-CoA Reductase Inhibitor", "EPC")]},
    {"key": "beta-blockers",
     "patterns": [r"beta[- ](adrenergic\s+)?block(ers?|ing\s+agents?)"],
     "rxclass": [("beta-Adrenergic Blocker", "EPC")]},
    {"key": "calcium-channel-blockers",
     "patterns": [r"calcium\s+channel\s+block(ers?|ing)"],
     "rxclass": [("Calcium Channel Blocker", "EPC")]},
    {"key": "ssris",
     "patterns": [r"\bSSRIs?\b", r"selective\s+serotonin\s+reuptake\s+inhibitors?"],
     "rxclass": [("Serotonin Reuptake Inhibitor", "EPC")],
     "exclude": ["trazodone"]},  # an SARI, not what a label means by "SSRIs"
    {"key": "maois",
     "patterns": [r"\bMAOIs?\b", r"monoamine\s+oxidase\s+inhibitors?"],
     "rxclass": [("Monoamine Oxidase Inhibitor", "EPC")]},
    {"key": "opioids",
     "patterns": [r"\bopioids?\b"],
     "rxclass": [("Opioid Agonist", "EPC")],
     "exclude": ["loperamide"]},  # gut-acting; not what an opioid CNS warning means
    {"key": "benzodiazepines",
     "patterns": [r"benzodiazepines?"],
     "rxclass": [("Benzodiazepine", "EPC")]},
    # CYP3A4: RxClass ignores strength, lists substrates such as ticagrelor as
    # inhibitors, and misses rifampin and phenytoin as inducers. These follow
    # the FDA's "Table of Substrates, Inhibitors and Inducers" instead, and the
    # label's own word ("strong", "moderate") picks the list.
    {"key": "cyp3a4-strong-inhibitors",
     "patterns": [rf"^(?!.*moderate).*strong\s+{_CYP}\s+inhibitors?"],
     "ingredients": _STRONG_INHIBITORS},
    {"key": "cyp3a4-moderate-inhibitors",
     "patterns": [rf"^(?!.*strong).*moderate\s+{_CYP}\s+inhibitors?"],
     "ingredients": _MODERATE_INHIBITORS},
    {"key": "cyp3a4-inhibitors",
     "patterns": [rf"{_CYP}\s+inhibitors?", rf"inhibitors?\s+of\s+{_CYP}"],
     "ingredients": _STRONG_INHIBITORS + _MODERATE_INHIBITORS},
    {"key": "cyp3a4-strong-inducers",
     "patterns": [rf"^(?!.*moderate).*strong\s+{_CYP}\s+inducers?"],
     "ingredients": _STRONG_INDUCERS},
    {"key": "cyp3a4-inducers",
     "patterns": [rf"{_CYP}\s+inducers?", rf"inducers?\s+of\s+{_CYP}"],
     "ingredients": _STRONG_INDUCERS + _MODERATE_INDUCERS},
]

_COMPILED = [(e["key"], [re.compile(p, re.IGNORECASE) for p in e["patterns"]]) for e in CLASS_MAP]


def match_class(phrase: str) -> str | None:
    """The class key a label's class phrase refers to, or None if it is not mapped."""
    if not phrase or not phrase.strip():
        return None
    for key, patterns in _COMPILED:
        if any(p.search(phrase) for p in patterns):
            return key
    return None
