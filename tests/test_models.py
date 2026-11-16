"""Tests for the data models."""
from clinical_pre_mortem_agent.models import (
    CarePlan, Finding, Medication, PatientRecord, PlanEdit,
)


def _patient(**kw):
    defaults = dict(patient_id="T-1", display_name="Mrs Test (synthetic)",
                    age_years=70, egfr=80.0, weight_kg=70.0)
    defaults.update(kw)
    return PatientRecord(**defaults)


def test_medication_daily_dose():
    med = Medication("amoxicillin", 500, 3)
    assert med.daily_dose_mg == 1500


def test_plan_copy_with_does_not_mutate():
    plan = CarePlan("P-1", _patient(), [Medication("warfarin", 5, 1)])
    edited = plan.copy_with(follow_up_days=7)
    assert plan.follow_up_days is None
    assert edited.follow_up_days == 7
    assert edited.medications == plan.medications


def test_finding_risk_score_is_severity_times_plausibility():
    finding = Finding("missed_allergy", "amoxicillin", "detail", ("evidence",),
                      severity=5, plausibility=0.85)
    assert finding.risk_score == 5 * 0.85


def test_plan_edit_is_valid_only_when_it_kills_and_adds_nothing():
    assert PlanEdit("x", "d", "a", "d", True, False).is_valid
    assert not PlanEdit("x", "d", "a", "d", False, False).is_valid
    assert not PlanEdit("x", "d", "a", "d", True, True).is_valid


def test_report_to_dict_round_trips_categories():
    from clinical_pre_mortem_agent import run_pre_mortem, sample_plan
    report = run_pre_mortem(sample_plan())
    data = report.to_dict()
    assert data["plan_id"] == "DEMO-1"
    assert data["verdict"] == "RISKS FOUND"
    assert {f["category"] for f in data["findings"]} == {"drug_interaction", "unmonitored_lab"}
    assert data["edits"][0]["is_valid"] is True
