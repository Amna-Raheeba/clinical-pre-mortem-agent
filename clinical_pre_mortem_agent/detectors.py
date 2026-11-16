"""The rule engine: six deterministic detectors, one per taxonomy category.

Each detector reads only the plan and the patient record and returns a
list of :class:`~models.Finding` objects. No detector calls a model, a
network, or anything non-deterministic — the same plan always produces
the same findings, which is what makes the evaluation reproducible and
the minimal-edit check meaningful (an edit "kills" a failure exactly when
the detector stops firing).
"""
from __future__ import annotations

from . import knowledge as kb
from .models import CarePlan, Finding
from .taxonomy import SEVERITY


def _drug_names(plan: CarePlan) -> set[str]:
    return {m.name.lower() for m in plan.medications}


def _allergy_hit(plan: CarePlan, drug: str) -> tuple[bool, str]:
    """True if the drug matches a recorded allergy (exact or by class)."""
    drug = drug.lower()
    for allergy in plan.patient.allergies:
        allergy = allergy.lower()
        if allergy == drug:
            return True, f"allergy: {allergy} (exact match)"
        if allergy in kb.ALLERGY_CLASSES and drug in kb.ALLERGY_CLASSES[allergy]:
            return True, f"allergy: {allergy} class contains {drug}"
    return False, ""


def detect_missed_allergy(plan: CarePlan) -> list[Finding]:
    findings = []
    if not plan.patient.allergies_known:
        return findings  # abstention handles this; the detector stays silent
    for med in plan.medications:
        hit, evidence = _allergy_hit(plan, med.name)
        if hit:
            exact = "(exact match)" in evidence
            findings.append(Finding(
                category="missed_allergy",
                drug=med.name,
                detail=f"{med.name} prescribed despite recorded {evidence.split(':')[1].strip()} allergy",
                evidence=(evidence, f"prescribed: {med.name} {med.dose_mg} mg"),
                severity=SEVERITY["missed_allergy"],
                plausibility=1.0 if exact else 0.85,
                earliest_warning_sign=kb.WARNING_SIGNS["missed_allergy"],
            ))
    return findings


def detect_renal_dose_error(plan: CarePlan) -> list[Finding]:
    findings = []
    egfr = plan.patient.egfr
    if egfr is None:
        return findings  # abstention handles this
    for med in plan.medications:
        name = med.name.lower()
        # Gentamicin: weight-based, interval matters when eGFR is low.
        if name == "gentamicin":
            if plan.patient.weight_kg is None:
                continue  # abstention handles missing weight
            per_kg = med.daily_dose_mg / plan.patient.weight_kg
            if egfr < kb.GENTAMICIN_EGFR_THRESHOLD and per_kg > kb.GENTAMICIN_MAX_MG_PER_KG_PER_DAY:
                findings.append(Finding(
                    category="renal_dose_error",
                    drug=med.name,
                    detail=f"gentamicin {per_kg:.1f} mg/kg/day at eGFR {egfr:.0f} — above the "
                           f"{kb.GENTAMICIN_MAX_MG_PER_KG_PER_DAY} mg/kg/day limit for eGFR < 60",
                    evidence=(f"eGFR: {egfr}", f"weight: {plan.patient.weight_kg} kg",
                              f"daily dose: {med.daily_dose_mg:.0f} mg"),
                    severity=SEVERITY["renal_dose_error"],
                    plausibility=0.95,
                    earliest_warning_sign=kb.WARNING_SIGNS["renal_dose_error"],
                ))
            continue
        for threshold, max_daily in kb.RENAL_RULES.get(name, []):
            if egfr < threshold and med.daily_dose_mg > max_daily:
                if max_daily == 0:
                    detail = (f"{name} is contraindicated at eGFR {egfr:.0f} "
                              f"(below {threshold:.0f}) but prescribed at "
                              f"{med.daily_dose_mg:.0f} mg/day")
                    plausibility = 1.0
                else:
                    detail = (f"{name} {med.daily_dose_mg:.0f} mg/day exceeds the "
                              f"{max_daily:.0f} mg/day limit for eGFR below {threshold:.0f} "
                              f"(patient eGFR {egfr:.0f})")
                    plausibility = 0.9
                findings.append(Finding(
                    category="renal_dose_error",
                    drug=med.name,
                    detail=detail,
                    evidence=(f"eGFR: {egfr}", f"daily dose: {med.daily_dose_mg:.0f} mg"),
                    severity=SEVERITY["renal_dose_error"],
                    plausibility=plausibility,
                    earliest_warning_sign=kb.WARNING_SIGNS["renal_dose_error"],
                ))
                break  # one finding per drug: the strictest band that applies
    return findings


def detect_drug_interaction(plan: CarePlan) -> list[Finding]:
    findings = []
    names = _drug_names(plan)
    meds = {m.name.lower(): m for m in plan.medications}
    for pair, (description, severity) in kb.INTERACTIONS.items():
        a, b = sorted(pair)
        if a in names and b in names:
            new_one = meds[a].is_new or meds[b].is_new
            findings.append(Finding(
                category="drug_interaction",
                drug=f"{a} + {b}",
                detail=f"{description} — both prescribed together",
                evidence=(f"prescribed: {a}", f"prescribed: {b}",
                          "one drug newly started" if new_one else "both continued"),
                severity=severity,
                plausibility=1.0 if new_one else 0.9,
                earliest_warning_sign=kb.WARNING_SIGNS["drug_interaction"],
            ))
    return findings


def detect_missing_follow_up(plan: CarePlan) -> list[Finding]:
    findings = []
    for med in plan.medications:
        if not med.is_new:
            continue
        required = kb.FOLLOW_UP_REQUIRED.get(med.name.lower())
        if required is None:
            continue
        if plan.follow_up_days is None:
            findings.append(Finding(
                category="missing_follow_up",
                drug=med.name,
                detail=f"{med.name} newly started but no follow-up scheduled "
                       f"(required within {required} days)",
                evidence=(f"new drug: {med.name}", "follow-up: none scheduled"),
                severity=SEVERITY["missing_follow_up"],
                plausibility=0.85,
                earliest_warning_sign=kb.WARNING_SIGNS["missing_follow_up"],
            ))
        elif plan.follow_up_days > required:
            findings.append(Finding(
                category="missing_follow_up",
                drug=med.name,
                detail=f"{med.name} newly started with follow-up in {plan.follow_up_days} days, "
                       f"but required within {required} days",
                evidence=(f"new drug: {med.name}",
                          f"follow-up: {plan.follow_up_days} days"),
                severity=SEVERITY["missing_follow_up"],
                plausibility=0.75,
                earliest_warning_sign=kb.WARNING_SIGNS["missing_follow_up"],
            ))
    return findings


def detect_contradictory_instruction(plan: CarePlan) -> list[Finding]:
    findings = []
    # Same drug twice at different doses.
    seen: dict[str, float] = {}
    for med in plan.medications:
        key = med.name.lower()
        if key in seen and seen[key] != med.dose_mg:
            findings.append(Finding(
                category="contradictory_instruction",
                drug=med.name,
                detail=f"{med.name} prescribed twice at different doses "
                       f"({seen[key]:.0f} mg and {med.dose_mg:.0f} mg)",
                evidence=(f"dose 1: {seen[key]:.0f} mg", f"dose 2: {med.dose_mg:.0f} mg"),
                severity=SEVERITY["contradictory_instruction"],
                plausibility=0.9,
                earliest_warning_sign=kb.WARNING_SIGNS["contradictory_instruction"],
            ))
        seen[key] = med.dose_mg
    # Two NSAIDs at once (duplicate therapy).
    nsaids = [m.name for m in plan.medications
              if m.name.lower() in kb.ALLERGY_CLASSES["nsaid"]]
    if len(nsaids) >= 2:
        findings.append(Finding(
            category="contradictory_instruction",
            drug=" + ".join(nsaids),
            detail=f"duplicate NSAID therapy: {', '.join(nsaids)} prescribed together",
            evidence=tuple(f"prescribed: {n}" for n in nsaids),
            severity=SEVERITY["contradictory_instruction"],
            plausibility=0.7,
            earliest_warning_sign=kb.WARNING_SIGNS["contradictory_instruction"],
        ))
    # Written instructions that contradict each other.
    normalised = {i.strip().lower() for i in plan.instructions}
    flagged_instructions: set[str] = set()
    for a, b in kb.CONTRADICTORY_PAIRS:
        if a in normalised and b in normalised:
            findings.append(Finding(
                category="contradictory_instruction",
                drug="",
                detail=f"instructions contradict: '{a}' and '{b}' both written",
                evidence=(f"instruction: {a}", f"instruction: {b}"),
                severity=SEVERITY["contradictory_instruction"],
                plausibility=0.9,
                earliest_warning_sign=kb.WARNING_SIGNS["contradictory_instruction"],
            ))
            flagged_instructions.update((a, b))
    # Written instruction contradicts the drug's standard administration.
    # (Skipped when that instruction is already part of a contradictory
    # pair above, so one fault is never reported twice.)
    for med in plan.medications:
        correct = kb.ADMINISTRATION.get(med.name.lower())
        if not correct:
            continue
        wrong = "take on an empty stomach" if correct == "take with food" else "take with food"
        if wrong in normalised and wrong not in flagged_instructions:
            findings.append(Finding(
                category="contradictory_instruction",
                drug=med.name,
                detail=f"instruction says '{wrong}' but {med.name} should be taken "
                       f"'{correct}'",
                evidence=(f"instruction: {wrong}", f"standard: {correct}"),
                severity=SEVERITY["contradictory_instruction"],
                plausibility=0.9,
                earliest_warning_sign=kb.WARNING_SIGNS["contradictory_instruction"],
            ))
    return findings


def detect_unmonitored_lab(plan: CarePlan) -> list[Finding]:
    findings = []
    ordered = {lab.lower() for lab in plan.monitoring_labs}
    for med in plan.medications:
        required = kb.MONITORING_REQUIRED.get(med.name.lower())
        if not required:
            continue
        missing = [lab for lab in required if lab.lower() not in ordered]
        if missing:
            findings.append(Finding(
                category="unmonitored_lab",
                drug=med.name,
                detail=f"{med.name} requires monitoring ({', '.join(required)}) but "
                       f"missing: {', '.join(missing)}",
                evidence=(f"prescribed: {med.name}",
                          f"ordered labs: {', '.join(sorted(ordered)) or 'none'}"),
                severity=SEVERITY["unmonitored_lab"],
                plausibility=0.8,
                earliest_warning_sign=kb.WARNING_SIGNS["unmonitored_lab"],
            ))
    return findings


DETECTORS = {
    "missed_allergy": detect_missed_allergy,
    "renal_dose_error": detect_renal_dose_error,
    "drug_interaction": detect_drug_interaction,
    "missing_follow_up": detect_missing_follow_up,
    "contradictory_instruction": detect_contradictory_instruction,
    "unmonitored_lab": detect_unmonitored_lab,
}


def run_all_detectors(plan: CarePlan) -> list[Finding]:
    """Run every detector on a plan and return all findings."""
    findings: list[Finding] = []
    for detector in DETECTORS.values():
        findings.extend(detector(plan))
    return findings
