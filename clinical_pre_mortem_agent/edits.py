"""Minimal plan edits: the one change that kills a failure.

For each top-ranked failure, propose the smallest change to the plan
that removes it — substitute one drug, reduce one dose, hold one drug,
schedule the missing follow-up, fix the contradictory instruction, or
order the missing lab. The edit is then *verified*: it is applied to a
copy of the plan and the detectors are re-run. The edit counts only if
the target failure no longer fires *and* no new failure appears. An
edit that trades one failure for another is reported as invalid, not
hidden.
"""
from __future__ import annotations

from . import knowledge as kb
from .detectors import run_all_detectors
from .models import CarePlan, Finding, Medication, PlanEdit


def _find_med(plan: CarePlan, name: str) -> Medication | None:
    for med in plan.medications:
        if med.name.lower() == name.lower():
            return med
    return None


def _replace_med(plan: CarePlan, old: Medication, new: Medication) -> CarePlan:
    meds = [new if m is old else m for m in plan.medications]
    return plan.copy_with(medications=meds)


def _remove_med(plan: CarePlan, name: str) -> CarePlan:
    meds = [m for m in plan.medications if m.name.lower() != name.lower()]
    return plan.copy_with(medications=meds)


def propose_edit(plan: CarePlan, finding: Finding) -> PlanEdit | None:
    """Propose the minimal edit for one finding, or None if none exists."""
    cat = finding.category

    if cat == "missed_allergy":
        drug = finding.drug
        alt = kb.ALTERNATIVES.get(drug.lower())
        if alt is None:
            edited = _remove_med(plan, drug)
            return _verified(plan, edited, finding,
                             f"stop {drug} (no safe substitute in the demo table)",
                             f"Removed {drug}; no substitute listed for this drug.")
        substitute, note = alt
        old = _find_med(plan, drug)
        if old is None:
            return None
        new = Medication(name=substitute, dose_mg=old.dose_mg,
                         doses_per_day=old.doses_per_day, is_new=old.is_new,
                         route=old.route)
        edited = _replace_med(plan, old, new)
        return _verified(plan, edited, finding,
                         f"substitute {drug} -> {substitute}",
                         f"Replaced {drug} with {substitute} ({note}).")

    if cat == "renal_dose_error":
        drug = finding.drug
        med = _find_med(plan, drug)
        if med is None:
            return None
        if drug.lower() == "gentamicin":
            # Reduce to the per-kg limit at the recorded weight.
            weight = plan.patient.weight_kg
            if weight is None:
                return None
            max_daily = kb.GENTAMICIN_MAX_MG_PER_KG_PER_DAY * weight
            new_dose = max_daily / med.doses_per_day
            new = Medication(name=med.name, dose_mg=new_dose,
                             doses_per_day=med.doses_per_day, is_new=med.is_new,
                             route=med.route)
            edited = _replace_med(plan, med, new)
            return _verified(plan, edited, finding,
                             f"reduce gentamicin to {new_dose:.0f} mg x {med.doses_per_day}/day",
                             f"Reduced gentamicin to the {kb.GENTAMICIN_MAX_MG_PER_KG_PER_DAY} "
                             f"mg/kg/day limit for this weight and eGFR.")
        egfr = plan.patient.egfr
        if egfr is None:
            return None
        for threshold, max_daily in kb.RENAL_RULES.get(drug.lower(), []):
            if egfr < threshold:
                if max_daily == 0:
                    edited = _remove_med(plan, drug)
                    return _verified(plan, edited, finding,
                                     f"stop {drug} (contraindicated at eGFR {egfr:.0f})",
                                     f"Stopped {drug}: contraindicated below eGFR {threshold:.0f}.")
                new_dose = max_daily / med.doses_per_day
                new = Medication(name=med.name, dose_mg=new_dose,
                                 doses_per_day=med.doses_per_day,
                                 is_new=med.is_new, route=med.route)
                edited = _replace_med(plan, med, new)
                return _verified(plan, edited, finding,
                                 f"reduce {drug} to {new_dose:.0f} mg x {med.doses_per_day}/day",
                                 f"Reduced {drug} to the {max_daily:.0f} mg/day limit "
                                 f"for eGFR below {threshold:.0f}.")
        return None

    if cat == "drug_interaction":
        a, b = [part.strip() for part in finding.drug.split("+")]
        # Hold the newly started drug; if neither is new, hold the second.
        med_a, med_b = _find_med(plan, a), _find_med(plan, b)
        hold = med_b if (med_b and med_b.is_new) else (med_a if med_a and med_a.is_new else med_b)
        if hold is None:
            return None
        edited = _remove_med(plan, hold.name)
        return _verified(plan, edited, finding,
                         f"hold {hold.name} while the other drug continues",
                         f"Held {hold.name} for the duration of the interacting course; "
                         f"review before restarting.")

    if cat == "missing_follow_up":
        drug = finding.drug
        required = kb.FOLLOW_UP_REQUIRED.get(drug.lower())
        if required is None:
            return None
        edited = plan.copy_with(follow_up_days=required)
        return _verified(plan, edited, finding,
                         f"schedule follow-up within {required} days",
                         f"Scheduled follow-up in {required} days for newly started {drug}.")

    if cat == "contradictory_instruction":
        # Duplicate dose: keep the first listed dose, drop the second.
        meds = [m for m in plan.medications]
        seen: dict[str, Medication] = {}
        deduped: list[Medication] = []
        changed = False
        for med in meds:
            key = med.name.lower()
            if key in seen and seen[key].dose_mg != med.dose_mg:
                changed = True
                continue  # drop the conflicting duplicate
            seen[key] = med
            deduped.append(med)
        # Duplicate NSAID: keep the first, drop the rest.
        nsaid_seen = False
        kept: list[Medication] = []
        for med in deduped:
            if med.name.lower() in kb.ALLERGY_CLASSES["nsaid"]:
                if nsaid_seen:
                    changed = True
                    continue
                nsaid_seen = True
            kept.append(med)
        # Contradictory written instructions: drop the wrong one.
        instructions = list(plan.instructions)
        normalised = {i.strip().lower() for i in instructions}
        for a_text, b_text in kb.CONTRADICTORY_PAIRS:
            if a_text in normalised and b_text in normalised:
                # Keep the instruction that matches a drug's standard
                # administration; otherwise keep the first listed.
                keep = None
                for med in kept:
                    correct = kb.ADMINISTRATION.get(med.name.lower())
                    if correct in (a_text, b_text):
                        keep = correct
                        break
                drop = b_text if keep == a_text else a_text
                instructions = [i for i in instructions if i.strip().lower() != drop]
                changed = True
        # Instruction vs drug standard: drop the wrong instruction.
        for med in kept:
            correct = kb.ADMINISTRATION.get(med.name.lower())
            if not correct:
                continue
            wrong = ("take on an empty stomach" if correct == "take with food"
                     else "take with food")
            if wrong in {i.strip().lower() for i in instructions}:
                instructions = [i for i in instructions if i.strip().lower() != wrong]
                changed = True
        if not changed:
            return None
        edited = plan.copy_with(medications=kept, instructions=tuple(instructions))
        return _verified(plan, edited, finding,
                         "resolve the contradictory instruction/dose",
                         "Kept one consistent dose and instruction; removed the conflicting entry.")

    if cat == "unmonitored_lab":
        drug = finding.drug
        required = kb.MONITORING_REQUIRED.get(drug.lower())
        if not required:
            return None
        ordered = list(plan.monitoring_labs)
        for lab in required:
            if lab.lower() not in {o.lower() for o in ordered}:
                ordered.append(lab)
        edited = plan.copy_with(monitoring_labs=tuple(ordered))
        return _verified(plan, edited, finding,
                         f"order monitoring labs: {', '.join(required)}",
                         f"Ordered {', '.join(required)} for {drug}.")

    return None


def _verified(original: CarePlan, edited: CarePlan, finding: Finding,
              action: str, description: str) -> PlanEdit:
    """Re-run the detectors on the edited plan and verify the edit."""
    after = run_all_detectors(edited)
    still_fires = any(
        f.category == finding.category and _same_target(f, finding) for f in after
    )
    before_keys = {(f.category, f.drug) for f in run_all_detectors(original)}
    new_failures = any((f.category, f.drug) not in before_keys for f in after)
    return PlanEdit(
        target_category=finding.category,
        drug=finding.drug,
        action=action,
        description=description,
        kills_failure=not still_fires,
        introduces_new_failure=new_failures,
    )


def _same_target(a: Finding, b: Finding) -> bool:
    """Whether two findings concern the same drug(s) in the same category."""
    return a.drug == b.drug
