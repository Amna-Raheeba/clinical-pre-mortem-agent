"""Evaluation: seeded synthetic plans with injected faults, four metrics.

The dataset is built by hand from archetypes, not sampled from real
data — there is no real data here. Each faulty plan carries exactly one
injected fault from one taxonomy category; each clean plan carries none;
each evidence-absent plan is missing the one value a category needs.

Metrics (all measured on this dataset, nothing else):

- **failure_recall** — injected faults the detectors found / injected.
- **false_alarm_rate** — clean plans with >= 1 finding / clean plans.
- **minimal_edit_success** — top-ranked failures whose proposed edit is
  verified (kills the failure, introduces nothing new) / edits proposed.
- **abstention_rate** — evidence-absent plans where the agent abstained
  on the right category / evidence-absent plans.

Honest limit, stated in the README and the experiment log: the faults
are injected from the same knowledge base the detectors read, so
failure_recall measures consistency between the generator and the
detectors — not how the agent would do on faults invented by someone
else. The false-alarm rate on clean plans is the more informative
number, because the clean plans were written to be genuinely safe.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from .models import CarePlan, LabResult, Medication, PatientRecord
from .pre_mortem import run_pre_mortem

SEED = 20261117


@dataclass
class EvalCase:
    plan: CarePlan
    injected: frozenset  # categories deliberately injected (empty = clean)
    expected_abstention: str | None = None  # category that must abstain


def _patient(pid: str, name: str, egfr=85.0, weight=70.0,
             allergies=(), allergies_known=True,
             conditions=()) -> PatientRecord:
    return PatientRecord(
        patient_id=pid, display_name=name, age_years=68, sex="F",
        weight_kg=weight, egfr=egfr, allergies=tuple(allergies),
        allergies_known=allergies_known, conditions=tuple(conditions),
    )


def _base_plan(pid: str, patient: PatientRecord, meds, **kw) -> CarePlan:
    defaults = dict(plan_id=pid, patient=patient, medications=list(meds),
                    follow_up_days=30, monitoring_labs=(), instructions=())
    defaults.update(kw)
    return CarePlan(**defaults)


def build_eval_dataset() -> list[EvalCase]:
    """42 seeded cases: 24 faulty (4 per category), 12 clean, 6 evidence-absent."""
    cases: list[EvalCase] = []

    # ------------------------------------------------ missed allergy (4)
    p = _patient("FA-1", "Mrs A (synthetic)", allergies=("penicillin",))
    cases.append(EvalCase(_base_plan("FA-1", p, [Medication("amoxicillin", 500, 3, is_new=True)],
                                     indication="chest infection"),
                          frozenset({"missed_allergy"})))
    p = _patient("FA-2", "Mr B (synthetic)", allergies=("sulfa",))
    cases.append(EvalCase(_base_plan("FA-2", p, [Medication("co-trimoxazole", 960, 2, is_new=True)],
                                     indication="urinary infection"),
                          frozenset({"missed_allergy"})))
    p = _patient("FA-3", "Mrs C (synthetic)", allergies=("amoxicillin",))
    cases.append(EvalCase(_base_plan("FA-3", p, [Medication("amoxicillin", 500, 3, is_new=True)],
                                     indication="chest infection"),
                          frozenset({"missed_allergy"})))
    p = _patient("FA-4", "Mr D (synthetic)", allergies=("nsaid",))
    cases.append(EvalCase(_base_plan("FA-4", p, [Medication("ibuprofen", 400, 3, is_new=True)],
                                     indication="joint pain"),
                          frozenset({"missed_allergy"})))

    # ------------------------------------------------ renal dose error (4)
    p = _patient("FR-1", "Mrs E (synthetic)", egfr=25.0)
    cases.append(EvalCase(_base_plan("FR-1", p, [Medication("metformin", 1000, 2)],
                                     indication="type 2 diabetes"),
                          frozenset({"renal_dose_error"})))
    p = _patient("FR-2", "Mr F (synthetic)", egfr=40.0)
    cases.append(EvalCase(_base_plan("FR-2", p, [Medication("gabapentin", 800, 3)],
                                     indication="neuropathic pain"),
                          frozenset({"renal_dose_error"})))
    p = _patient("FR-3", "Mrs G (synthetic)", egfr=20.0)
    cases.append(EvalCase(_base_plan("FR-3", p, [Medication("ciprofloxacin", 500, 2, is_new=True)],
                                     indication="urinary infection"),
                          frozenset({"renal_dose_error"})))
    p = _patient("FR-4", "Mr H (synthetic)", egfr=50.0, weight=60.0)
    cases.append(EvalCase(_base_plan("FR-4", p, [Medication("gentamicin", 240, 2, is_new=True)],
                                     monitoring_labs=("creatinine", "gentamicin level"),
                                     indication="sepsis"),
                          frozenset({"renal_dose_error"})))

    # ------------------------------------------------ drug interaction (4)
    p = _patient("FI-1", "Mrs I (synthetic)")
    cases.append(EvalCase(_base_plan("FI-1", p, [Medication("warfarin", 5, 1),
                                                 Medication("ibuprofen", 400, 3, is_new=True)],
                                     monitoring_labs=("INR",),
                                     indication="atrial fibrillation"),
                          frozenset({"drug_interaction"})))
    p = _patient("FI-2", "Mr J (synthetic)")
    cases.append(EvalCase(_base_plan("FI-2", p, [Medication("warfarin", 5, 1),
                                                 Medication("ciprofloxacin", 500, 2, is_new=True)],
                                     monitoring_labs=("INR",),
                                     indication="atrial fibrillation"),
                          frozenset({"drug_interaction"})))
    p = _patient("FI-3", "Mrs K (synthetic)")
    cases.append(EvalCase(_base_plan("FI-3", p, [Medication("lisinopril", 10, 1),
                                                 Medication("spironolactone", 25, 1, is_new=True)],
                                     monitoring_labs=("potassium", "creatinine"),
                                     indication="heart failure"),
                          frozenset({"drug_interaction"})))
    p = _patient("FI-4", "Mr L (synthetic)")
    cases.append(EvalCase(_base_plan("FI-4", p, [Medication("simvastatin", 40, 1),
                                                 Medication("clarithromycin", 500, 2, is_new=True)],
                                     indication="high cholesterol"),
                          frozenset({"drug_interaction"})))

    # ------------------------------------------------ missing follow-up (4)
    p = _patient("FF-1", "Mrs M (synthetic)")
    cases.append(EvalCase(_base_plan("FF-1", p, [Medication("warfarin", 5, 1, is_new=True)],
                                     follow_up_days=None, monitoring_labs=("INR",),
                                     indication="atrial fibrillation"),
                          frozenset({"missing_follow_up"})))
    p = _patient("FF-2", "Mr N (synthetic)")
    cases.append(EvalCase(_base_plan("FF-2", p, [Medication("warfarin", 5, 1, is_new=True)],
                                     follow_up_days=30, monitoring_labs=("INR",),
                                     indication="atrial fibrillation"),
                          frozenset({"missing_follow_up"})))
    p = _patient("FF-3", "Mrs O (synthetic)")
    cases.append(EvalCase(_base_plan("FF-3", p, [Medication("insulin", 10, 1, is_new=True)],
                                     follow_up_days=None,
                                     indication="type 2 diabetes"),
                          frozenset({"missing_follow_up"})))
    p = _patient("FF-4", "Mr P (synthetic)")
    cases.append(EvalCase(_base_plan("FF-4", p, [Medication("methotrexate", 15, 1, is_new=True)],
                                     follow_up_days=60,
                                     monitoring_labs=("CBC", "ALT"),
                                     indication="rheumatoid arthritis"),
                          frozenset({"missing_follow_up"})))

    # ------------------------------------------------ contradictory instruction (4)
    p = _patient("FC-1", "Mrs Q (synthetic)")
    cases.append(EvalCase(_base_plan("FC-1", p, [Medication("amoxicillin", 500, 3, is_new=True),
                                                 Medication("amoxicillin", 250, 3)],
                                     indication="chest infection"),
                          frozenset({"contradictory_instruction"})))
    p = _patient("FC-2", "Mr R (synthetic)")
    cases.append(EvalCase(_base_plan("FC-2", p, [Medication("ibuprofen", 400, 3, is_new=True),
                                                 Medication("naproxen", 500, 2)],
                                     indication="joint pain"),
                          frozenset({"contradictory_instruction"})))
    p = _patient("FC-3", "Mrs S (synthetic)")
    cases.append(EvalCase(_base_plan("FC-3", p, [Medication("levothyroxine", 100, 1)],
                                     instructions=("take with food", "take on an empty stomach"),
                                     indication="hypothyroidism"),
                          frozenset({"contradictory_instruction"})))
    p = _patient("FC-4", "Mr T (synthetic)")
    cases.append(EvalCase(_base_plan("FC-4", p, [Medication("ibuprofen", 400, 3, is_new=True)],
                                     instructions=("take on an empty stomach",),
                                     indication="joint pain"),
                          frozenset({"contradictory_instruction"})))

    # ------------------------------------------------ unmonitored lab (4)
    p = _patient("FU-1", "Mrs U (synthetic)")
    cases.append(EvalCase(_base_plan("FU-1", p, [Medication("warfarin", 5, 1, is_new=True)],
                                     follow_up_days=7, monitoring_labs=(),
                                     indication="atrial fibrillation"),
                          frozenset({"unmonitored_lab"})))
    p = _patient("FU-2", "Mr V (synthetic)")
    cases.append(EvalCase(_base_plan("FU-2", p, [Medication("lisinopril", 10, 1, is_new=True)],
                                     follow_up_days=30, monitoring_labs=("creatinine",),
                                     indication="hypertension"),
                          frozenset({"unmonitored_lab"})))
    p = _patient("FU-3", "Mrs W (synthetic)")
    cases.append(EvalCase(_base_plan("FU-3", p, [Medication("methotrexate", 15, 1, is_new=True)],
                                     follow_up_days=30, monitoring_labs=("CBC",),
                                     indication="rheumatoid arthritis"),
                          frozenset({"unmonitored_lab"})))
    p = _patient("FU-4", "Mr X (synthetic)")
    cases.append(EvalCase(_base_plan("FU-4", p, [Medication("lithium", 400, 2, is_new=True)],
                                     follow_up_days=30, monitoring_labs=(),
                                     indication="bipolar disorder"),
                          frozenset({"unmonitored_lab"})))

    # ------------------------------------------------ clean plans (12)
    clean_specs = [
        ("C-01", "Mrs Y (synthetic)", [Medication("amoxicillin", 500, 3, is_new=True)],
         dict(indication="chest infection")),
        ("C-02", "Mr Z (synthetic)", [Medication("paracetamol", 1000, 4, is_new=True)],
         dict(indication="pain")),
        ("C-03", "Mrs AA (synthetic)", [Medication("lisinopril", 10, 1, is_new=True)],
         dict(indication="hypertension", monitoring_labs=("potassium", "creatinine"))),
        ("C-04", "Mr AB (synthetic)", [Medication("warfarin", 5, 1, is_new=True)],
         dict(indication="atrial fibrillation", follow_up_days=7,
              monitoring_labs=("INR",))),
        ("C-05", "Mrs AC (synthetic)", [Medication("metformin", 500, 2)],
         dict(indication="type 2 diabetes")),
        ("C-06", "Mr AD (synthetic)", [Medication("levothyroxine", 100, 1)],
         dict(indication="hypothyroidism", instructions=("take on an empty stomach",))),
        ("C-07", "Mrs AE (synthetic)", [Medication("atorvastatin", 20, 1)],
         dict(indication="high cholesterol")),
        ("C-08", "Mr AF (synthetic)", [Medication("methotrexate", 15, 1, is_new=True)],
         dict(indication="rheumatoid arthritis", follow_up_days=30,
              monitoring_labs=("CBC", "ALT"))),
        ("C-09", "Mrs AG (synthetic)", [Medication("amoxicillin", 500, 3, is_new=True),
                                         Medication("paracetamol", 1000, 4)],
         dict(indication="chest infection")),
        ("C-10", "Mr AH (synthetic)", [Medication("ibuprofen", 400, 3, is_new=True)],
         dict(indication="joint pain", instructions=("take with food",))),
        ("C-11", "Mrs AI (synthetic)", [Medication("gabapentin", 300, 3)],
         dict(indication="neuropathic pain")),
        ("C-12", "Mr AJ (synthetic)", [Medication("ciprofloxacin", 500, 2, is_new=True)],
         dict(indication="urinary infection")),
    ]
    for pid, name, meds, kw in clean_specs:
        cases.append(EvalCase(_base_plan(pid, _patient(pid, name), meds, **kw),
                              frozenset()))

    # ------------------------------------------------ evidence-absent plans (6)
    p = PatientRecord(patient_id="E-1", display_name="Mrs AK (synthetic)",
                      age_years=72, sex="F", weight_kg=70.0, egfr=None)
    cases.append(EvalCase(_base_plan("E-1", p, [Medication("metformin", 1000, 2)],
                                     indication="type 2 diabetes"),
                          frozenset(), expected_abstention="renal_dose_error"))
    p = PatientRecord(patient_id="E-2", display_name="Mr AL (synthetic)",
                      age_years=70, sex="M", weight_kg=80.0, egfr=None)
    cases.append(EvalCase(_base_plan("E-2", p, [Medication("gabapentin", 600, 3)],
                                     indication="neuropathic pain"),
                          frozenset(), expected_abstention="renal_dose_error"))
    p = PatientRecord(patient_id="E-3", display_name="Mrs AM (synthetic)",
                      age_years=65, sex="F", weight_kg=65.0, egfr=80.0,
                      allergies_known=False)
    cases.append(EvalCase(_base_plan("E-3", p, [Medication("amoxicillin", 500, 3, is_new=True)],
                                     indication="chest infection"),
                          frozenset(), expected_abstention="missed_allergy"))
    p = PatientRecord(patient_id="E-4", display_name="Mr AN (synthetic)",
                      age_years=66, sex="M", weight_kg=75.0, egfr=78.0,
                      allergies_known=False)
    cases.append(EvalCase(_base_plan("E-4", p, [Medication("co-trimoxazole", 960, 2, is_new=True)],
                                     indication="urinary infection"),
                          frozenset(), expected_abstention="missed_allergy"))
    p = PatientRecord(patient_id="E-5", display_name="Mrs AO (synthetic)",
                      age_years=74, sex="F", weight_kg=None, egfr=45.0)
    cases.append(EvalCase(_base_plan("E-5", p, [Medication("gentamicin", 240, 2, is_new=True)],
                                     monitoring_labs=("creatinine", "gentamicin level"),
                                     indication="sepsis"),
                          frozenset(), expected_abstention="renal_dose_error"))
    p = PatientRecord(patient_id="E-6", display_name="Mr AP (synthetic)",
                      age_years=71, sex="M", weight_kg=82.0, egfr=None)
    cases.append(EvalCase(_base_plan("E-6", p, [Medication("ciprofloxacin", 500, 2, is_new=True)],
                                     indication="urinary infection"),
                          frozenset(), expected_abstention="renal_dose_error"))

    return cases


def evaluate(cases: list[EvalCase] | None = None) -> dict:
    """Run the pre-mortem on every case and compute the four metrics."""
    if cases is None:
        cases = build_eval_dataset()

    rows = []
    injected_total = 0
    injected_found = 0
    clean_total = 0
    clean_with_findings = 0
    edits_proposed = 0
    edits_valid = 0
    abstain_total = 0
    abstain_correct = 0

    for case in cases:
        report = run_pre_mortem(case.plan)
        found_categories = {f.category for f in report.findings}
        row = {
            "plan_id": case.plan.plan_id,
            "injected": sorted(case.injected),
            "found": sorted(found_categories),
            "verdict": report.verdict,
            "n_findings": len(report.findings),
            "n_edits": len(report.edits),
            "n_valid_edits": sum(1 for e in report.edits if e.is_valid),
            "abstentions": [a.category for a in report.abstentions],
        }
        rows.append(row)

        if case.injected:
            injected_total += len(case.injected)
            injected_found += len(case.injected & found_categories)
            for edit in report.edits:
                edits_proposed += 1
                if edit.is_valid:
                    edits_valid += 1
        elif case.expected_abstention is None:
            clean_total += 1
            if report.findings:
                clean_with_findings += 1
        if case.expected_abstention is not None:
            abstain_total += 1
            if case.expected_abstention in {a.category for a in report.abstentions}:
                abstain_correct += 1

    metrics = {
        "n_cases": len(cases),
        "n_faulty": sum(1 for c in cases if c.injected),
        "n_clean": clean_total,
        "n_evidence_absent": abstain_total,
        "failure_recall": round(injected_found / injected_total, 4) if injected_total else None,
        "injected_found": injected_found,
        "injected_total": injected_total,
        "false_alarm_rate": round(clean_with_findings / clean_total, 4) if clean_total else None,
        "clean_with_findings": clean_with_findings,
        "minimal_edit_success": round(edits_valid / edits_proposed, 4) if edits_proposed else None,
        "edits_valid": edits_valid,
        "edits_proposed": edits_proposed,
        "abstention_rate": round(abstain_correct / abstain_total, 4) if abstain_total else None,
        "abstain_correct": abstain_correct,
        "rows": rows,
    }
    return metrics


def write_results(metrics: dict, out_dir: Path) -> None:
    """Write results/evaluation.json and results/evaluation.csv."""
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {k: v for k, v in metrics.items() if k != "rows"}
    (out_dir / "evaluation.json").write_text(json.dumps(summary, indent=2) + "\n")
    with open(out_dir / "evaluation.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "plan_id", "injected", "found", "verdict",
            "n_findings", "n_edits", "n_valid_edits", "abstentions"])
        writer.writeheader()
        for row in metrics["rows"]:
            writer.writerow({
                "plan_id": row["plan_id"],
                "injected": ";".join(row["injected"]),
                "found": ";".join(row["found"]),
                "verdict": row["verdict"],
                "n_findings": row["n_findings"],
                "n_edits": row["n_edits"],
                "n_valid_edits": row["n_valid_edits"],
                "abstentions": ";".join(row["abstentions"]),
            })


def sample_plan() -> CarePlan:
    """One faulty demo plan: warfarin + ibuprofen, no INR, no follow-up."""
    patient = _patient("DEMO-1", "Mrs Demo (synthetic)", egfr=72.0)
    return _base_plan("DEMO-1", patient,
                      [Medication("warfarin", 5, 1),
                       Medication("ibuprofen", 400, 3, is_new=True)],
                      follow_up_days=None, monitoring_labs=(),
                      indication="atrial fibrillation with new joint pain")
