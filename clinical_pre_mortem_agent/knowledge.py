"""The demo knowledge base: a small, explicit rule table.

This is deliberately small and readable, not a clinical database. Every
rule is a standard, widely taught fact (allergy classes, renal dose
limits, classic interactions, monitoring requirements). It is a *demo*
knowledge base for a research prototype — it is not clinical guidance,
not a medical device, and must never be used on a real patient. The
README states this, and the evaluation measures the agent against faults
injected from this same table (a consistency check, not external
validity — see docs/experiment_log.md).
"""
from __future__ import annotations

# ---------------------------------------------------------------- allergies
# Allergy class -> drugs in that class (generic names, lowercase).
ALLERGY_CLASSES: dict[str, tuple[str, ...]] = {
    "penicillin": ("amoxicillin", "ampicillin", "penicillin", "piperacillin",
                   "flucloxacillin", "co-amoxiclav"),
    "sulfa": ("sulfamethoxazole", "sulfadiazine", "co-trimoxazole"),
    "nsaid": ("ibuprofen", "naproxen", "diclofenac", "celecoxib", "ketorolac"),
}

# ---------------------------------------------------------------- renal dosing
# drug -> list of (eGFR threshold, max daily dose in mg). The first band
# whose threshold the patient's eGFR falls below applies; a max of 0
# means contraindicated at that eGFR.
RENAL_RULES: dict[str, list[tuple[float, float]]] = {
    # (eGFR below this, max mg/day)
    "metformin": [(30.0, 0.0), (45.0, 1000.0)],
    "gabapentin": [(15.0, 300.0), (30.0, 700.0), (60.0, 1400.0)],
    "ciprofloxacin": [(30.0, 500.0)],
    "allopurinol": [(30.0, 100.0), (60.0, 200.0)],
}

# Weight-based renal rule: gentamicin is dosed per kg and needs an
# extended interval when eGFR is low.
GENTAMICIN_MAX_MG_PER_KG_PER_DAY = 5.0
GENTAMICIN_EGFR_THRESHOLD = 60.0

# ---------------------------------------------------------------- interactions
# frozenset of two drugs -> (description, severity 1-5)
INTERACTIONS: dict[frozenset, tuple[str, int]] = {
    frozenset({"warfarin", "ibuprofen"}):
        ("NSAID added to warfarin raises major-bleed risk", 4),
    frozenset({"warfarin", "ciprofloxacin"}):
        ("Ciprofloxacin raises INR and bleed risk on warfarin", 4),
    frozenset({"lisinopril", "spironolactone"}):
        ("ACE inhibitor plus spironolactone risks hyperkalaemia", 4),
    frozenset({"simvastatin", "clarithromycin"}):
        ("Clarithromycin blocks simvastatin clearance; myopathy risk", 4),
    frozenset({"lithium", "ibuprofen"}):
        ("NSAID reduces lithium clearance; lithium toxicity risk", 4),
    frozenset({"methotrexate", "co-trimoxazole"}):
        ("Co-trimoxazole with methotrexate risks severe myelosuppression", 5),
}

# ---------------------------------------------------------------- monitoring
# drug -> labs that must be ordered for monitoring while on the drug.
MONITORING_REQUIRED: dict[str, tuple[str, ...]] = {
    "warfarin": ("INR",),
    "lisinopril": ("potassium", "creatinine"),
    "methotrexate": ("CBC", "ALT"),
    "amiodarone": ("TSH", "ALT"),
    "lithium": ("lithium level",),
    "gentamicin": ("creatinine", "gentamicin level"),
}

# ---------------------------------------------------------------- follow-up
# drug (when newly started) -> maximum days until follow-up.
FOLLOW_UP_REQUIRED: dict[str, int] = {
    "warfarin": 7,
    "insulin": 14,
    "lisinopril": 30,
    "methotrexate": 30,
    "amiodarone": 30,
    # Gentamicin levels must be reviewed within days of starting: a
    # weight-based, nephrotoxic drug with a narrow therapeutic window.
    "gentamicin": 3,
}

# ---------------------------------------------------------------- administration
# drug -> the correct administration instruction (used to spot
# contradictory instructions).
ADMINISTRATION: dict[str, str] = {
    "ibuprofen": "take with food",
    "metformin": "take with food",
    "levothyroxine": "take on an empty stomach",
    "alendronate": "take on an empty stomach",
    "ciprofloxacin": "take on an empty stomach",
}

# Pairs of instructions that contradict each other (normalised, lowercase).
CONTRADICTORY_PAIRS: tuple[tuple[str, str], ...] = (
    ("take with food", "take on an empty stomach"),
    ("take in the morning", "take at night"),
)

# ---------------------------------------------------------------- alternatives
# drug -> (substitute, note). Only used for the minimal-edit step, and only
# when the indication fits; the edit always names the substitution openly.
ALTERNATIVES: dict[str, tuple[str, str]] = {
    "amoxicillin": ("azithromycin", "macrolide alternative for respiratory infection"),
    "ampicillin": ("azithromycin", "macrolide alternative for respiratory infection"),
    "penicillin": ("azithromycin", "macrolide alternative for respiratory infection"),
    "ibuprofen": ("paracetamol", "non-NSAID analgesic"),
    "naproxen": ("paracetamol", "non-NSAID analgesic"),
    "diclofenac": ("paracetamol", "non-NSAID analgesic"),
    "sulfamethoxazole": ("nitrofurantoin", "alternative for uncomplicated UTI"),
    "co-trimoxazole": ("nitrofurantoin", "alternative for uncomplicated UTI"),
}

# ---------------------------------------------------------------- failure chains
# Second-order failure chains: (enabler category, enabled category, link).
# A chain exists when both findings fire AND they share a drug — the
# enabler is the failure that lets the enabled failure go undetected or
# unreviewed. The link text names the mechanism. This is a statement
# about this deterministic taxonomy, not a claim about real clinical
# causality: "enables" here means "removes the check that would have
# caught it", which is exactly what the rule engine can see.
CHAIN_LINKS: tuple[tuple[str, str, str], ...] = (
    ("unmonitored_lab", "renal_dose_error",
     "the missing lab is the test that would have revealed the drug accumulating"),
    ("unmonitored_lab", "drug_interaction",
     "the missing lab is the test that would have revealed the interaction's harm"),
    ("missing_follow_up", "drug_interaction",
     "the missed visit is where the interaction would have been caught"),
    ("missing_follow_up", "renal_dose_error",
     "the missed visit is where the dose would have been reviewed"),
)

# Earliest observable warning sign per failure category.
WARNING_SIGNS: dict[str, str] = {
    "missed_allergy": "rash, hives, or wheeze within hours of the first dose",
    "renal_dose_error": "rising creatinine and falling urine output over days",
    "drug_interaction": "unusual bruising, nosebleed, or melaena within the first week",
    "missing_follow_up": "no one notices the INR drifting until a bleed or clot",
    "contradictory_instruction": "a dose taken twice, then a dose missed entirely",
    "unmonitored_lab": "the monitored value drifting out of range with no test scheduled to catch it",
}
