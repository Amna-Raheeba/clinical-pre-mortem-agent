"""Abstention: refuse to judge a category when its evidence is absent.

A pre-mortem that guesses is worse than one that stays silent. When the
record lacks the evidence a detector needs, the agent abstains on that
category — openly, with the missing evidence named — instead of
reporting "no failure found". The evaluation measures this: on plans
with deliberately missing evidence, the abstention rate must be high.
"""
from __future__ import annotations

from . import knowledge as kb
from .models import Abstention, CarePlan


def check_abstentions(plan: CarePlan) -> list[Abstention]:
    abstentions: list[Abstention] = []
    patient = plan.patient

    # Allergy: cannot judge without an allergy history.
    if not patient.allergies_known:
        abstentions.append(Abstention(
            category="missed_allergy",
            reason="allergy history not recorded — cannot rule out a missed allergy",
        ))

    # Renal dosing: needs eGFR, and weight for weight-based drugs.
    renally_dosed = [m.name for m in plan.medications
                     if m.name.lower() in kb.RENAL_RULES or m.name.lower() == "gentamicin"]
    if renally_dosed:
        if patient.egfr is None:
            abstentions.append(Abstention(
                category="renal_dose_error",
                reason=f"eGFR not recorded but plan contains renally dosed drug(s): "
                       f"{', '.join(renally_dosed)}",
            ))
        elif any(m.name.lower() == "gentamicin" for m in plan.medications) \
                and patient.weight_kg is None:
            abstentions.append(Abstention(
                category="renal_dose_error",
                reason="weight not recorded — gentamicin is weight-based and cannot be checked",
            ))

    return abstentions
