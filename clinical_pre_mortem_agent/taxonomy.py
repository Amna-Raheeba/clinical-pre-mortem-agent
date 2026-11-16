"""The deterministic failure taxonomy: six failure categories.

A pre-mortem is only useful if the failures it imagines are the failures
that actually happen. These six are the classic, teachable prescribing
failures — each one is detectable from the plan and the record alone, with
no model and no guesswork. The verdict is code: a category fires only
when its rule matches the plan.
"""
from __future__ import annotations

CATEGORIES: tuple[str, ...] = (
    "missed_allergy",
    "renal_dose_error",
    "drug_interaction",
    "missing_follow_up",
    "contradictory_instruction",
    "unmonitored_lab",
)

# Human-readable statement of what each category means.
DESCRIPTIONS: dict[str, str] = {
    "missed_allergy": "A prescribed drug matches a recorded allergy.",
    "renal_dose_error": "A renally cleared drug is dosed above its eGFR limit.",
    "drug_interaction": "Two prescribed drugs interact dangerously.",
    "missing_follow_up": "A newly started high-risk drug has no timely follow-up.",
    "contradictory_instruction": "Written instructions contradict each other or the dose.",
    "unmonitored_lab": "A drug that needs monitoring labs has none ordered.",
}

# Fixed severity per category (1 low - 5 life-threatening). Severity is a
# property of the category, not of the patient; plausibility carries the
# patient-specific evidence.
SEVERITY: dict[str, int] = {
    "missed_allergy": 5,
    "renal_dose_error": 4,
    "drug_interaction": 4,
    "missing_follow_up": 3,
    "contradictory_instruction": 2,
    "unmonitored_lab": 3,
}
