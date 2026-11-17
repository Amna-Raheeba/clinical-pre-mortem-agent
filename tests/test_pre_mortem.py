"""Tests for the pre-mortem orchestrator and the evaluation harness."""
from clinical_pre_mortem_agent import run_pre_mortem, sample_plan
from clinical_pre_mortem_agent.evaluation import build_eval_dataset, evaluate
from clinical_pre_mortem_agent.models import CarePlan, Medication, PatientRecord


def _plan(meds, egfr=85.0, weight=70.0, allergies=(), allergies_known=True,
          follow_up_days=30, monitoring_labs=(), instructions=()):
    patient = PatientRecord(patient_id="T-1", display_name="Mrs Test (synthetic)",
                            age_years=70, egfr=egfr, weight_kg=weight,
                            allergies=tuple(allergies), allergies_known=allergies_known)
    return CarePlan("T-1", patient, list(meds), follow_up_days=follow_up_days,
                    monitoring_labs=tuple(monitoring_labs),
                    instructions=tuple(instructions))


def test_verdict_safe_on_clean_plan():
    plan = _plan([Medication("paracetamol", 1000, 4)])
    assert run_pre_mortem(plan).verdict == "SAFE"


def test_verdict_risks_found_on_faulty_plan():
    assert run_pre_mortem(sample_plan()).verdict == "RISKS FOUND"


def test_verdict_abstained_when_evidence_missing():
    plan = _plan([Medication("metformin", 1000, 2)], egfr=None)
    report = run_pre_mortem(plan)
    assert report.verdict == "ABSTAINED"
    assert report.findings == []


def test_verdict_combined_when_both():
    # Interaction found AND eGFR missing for a renally dosed drug.
    plan = _plan([Medication("warfarin", 5, 1), Medication("ibuprofen", 400, 3, is_new=True),
                  Medication("metformin", 500, 2)],
                 egfr=None, monitoring_labs=("INR",))
    report = run_pre_mortem(plan)
    assert report.verdict == "RISKS FOUND + ABSTAINED"


def test_only_top_two_failures_get_edits():
    plan = _plan([Medication("warfarin", 5, 1, is_new=True),
                  Medication("ibuprofen", 400, 3, is_new=True)],
                 follow_up_days=None, monitoring_labs=())
    report = run_pre_mortem(plan)
    assert len(report.findings) == 3
    assert len(report.edits) == 2
    assert all(e.is_valid for e in report.edits)


def test_edits_target_the_top_ranked_failures():
    plan = _plan([Medication("warfarin", 5, 1, is_new=True),
                  Medication("ibuprofen", 400, 3, is_new=True)],
                 follow_up_days=None, monitoring_labs=())
    report = run_pre_mortem(plan)
    assert {e.target_category for e in report.edits} == {
        f.category for f in report.ranked_findings[:2]}


def test_dataset_has_42_cases_with_the_right_split():
    cases = build_eval_dataset()
    assert len(cases) == 50
    assert sum(1 for c in cases if c.injected) == 32
    assert sum(1 for c in cases if c.expected_chains) == 8
    assert sum(1 for c in cases if not c.injected and c.expected_abstention is None) == 12
    assert sum(1 for c in cases if c.expected_abstention is not None) == 6


def test_dataset_covers_all_six_categories():
    cases = build_eval_dataset()
    covered = set()
    for case in cases:
        covered |= set(case.injected)
    assert covered == {"missed_allergy", "renal_dose_error", "drug_interaction",
                       "missing_follow_up", "contradictory_instruction",
                       "unmonitored_lab"}


def test_evaluation_metrics_are_measured_not_asserted():
    metrics = evaluate()
    assert metrics["failure_recall"] == 1.0
    assert metrics["injected_found"] == 40 and metrics["injected_total"] == 40
    assert metrics["false_alarm_rate"] == 0.0
    assert metrics["minimal_edit_success"] == 1.0
    assert metrics["abstention_rate"] == 1.0
    assert metrics["chain_recall"] == 1.0
    assert metrics["chains_found"] == 8 and metrics["chains_expected"] == 8
    assert metrics["chain_break_rate"] == 1.0
    assert metrics["chains_broken"] == 8 and metrics["chains_detected"] == 8
    assert metrics["false_chain_rate"] == 0.0
    assert len(metrics["rows"]) == 50
