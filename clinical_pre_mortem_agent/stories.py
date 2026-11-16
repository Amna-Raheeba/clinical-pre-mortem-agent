"""Failure stories: prose that explains a finding, never decides it.

The verdict is code (the detectors). The story is what a clinician
would read: assume the failure already happened, and narrate how the
plan got there, the earliest warning sign, and what would have stopped
it. Stories are generated *from* findings, so a story can never invent
a failure the detectors did not find.

Two storytellers exist behind one interface:

- :class:`MockStoryteller` — deterministic templates, offline, always
  available. This is what the evaluation, the CLI and the dashboard use.
- :class:`LLMStoryteller` — an optional adapter for a real language
  model. It raises :class:`StorytellerUnavailable` unless a model
  callable is supplied, so the offline path never pretends to be an LLM.
"""
from __future__ import annotations

from .models import CarePlan, Finding

TEMPLATES: dict[str, str] = {
    "missed_allergy": (
        "It is the evening of the first dose. {name} develops {sign}. "
        "The allergy was in the record — {evidence} — and {drug} was "
        "prescribed anyway. The failure was not a mystery: the record and "
        "the prescription were never compared."
    ),
    "renal_dose_error": (
        "Three days later, {name}'s creatinine has climbed and urine output "
        "has fallen. {drug} was dosed for a healthy kidney, not for an eGFR "
        "of {egfr}. The drug accumulated exactly as the dose predicted it "
        "would; the earliest sign was {sign}."
    ),
    "drug_interaction": (
        "Within the first week, {name} notices {sign}. Two drugs that should "
        "never have met — {drug} — were prescribed together. Either one alone "
        "was fine; together they produced the harm neither would cause alone."
    ),
    "missing_follow_up": (
        "Two weeks pass with no appointment. {name} is taking {drug} with "
        "nobody watching the number that matters. {sign} — and by the time "
        "anyone looks, the harm has already happened."
    ),
    "contradictory_instruction": (
        "By the end of the first week, {name} has missed doses and then "
        "doubled up to compensate. The written instructions said two "
        "opposite things, and the patient followed both. {sign}."
    ),
    "unmonitored_lab": (
        "Nothing looks wrong on the outside, which is the point: {drug} needs "
        "monitoring and none was ordered. The earliest sign would have been "
        "{sign}."
    ),
}


class StorytellerUnavailable(RuntimeError):
    """Raised when no storyteller backend is available."""


class MockStoryteller:
    """Deterministic, template-based storyteller (offline default)."""

    def tell(self, plan: CarePlan, finding: Finding) -> str:
        template = TEMPLATES[finding.category]
        egfr = plan.patient.egfr
        return template.format(
            name=plan.patient.display_name,
            drug=finding.drug or "the plan",
            sign=finding.earliest_warning_sign,
            evidence=", ".join(finding.evidence),
            egfr=f"{egfr:.0f}" if egfr is not None else "unknown",
        )


class LLMStoryteller:
    """Optional LLM-backed storyteller.

    Pass a callable ``generate(prompt) -> str``; without one, every call
    raises :class:`StorytellerUnavailable` instead of fabricating prose.
    The LLM is only ever asked to *narrate* a finding the detectors
    already produced — it cannot add, remove, or change a verdict.
    """

    def __init__(self, generate=None):
        self._generate = generate

    def tell(self, plan: CarePlan, finding: Finding) -> str:
        if self._generate is None:
            raise StorytellerUnavailable(
                "No language-model backend configured. Use MockStoryteller "
                "for the offline path."
            )
        prompt = (
            f"Write a short prospective-hindsight failure story (3-4 sentences) "
            f"for a synthetic patient, {plan.patient.display_name}, on a care plan "
            f"for {plan.indication or 'an undisclosed condition'}. The failure is: "
            f"{finding.detail}. The earliest warning sign is: "
            f"{finding.earliest_warning_sign}. Do not invent new failures."
        )
        return self._generate(prompt)
