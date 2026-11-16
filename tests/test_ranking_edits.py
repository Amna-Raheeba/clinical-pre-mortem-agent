"""Tests for ranking and minimal edits."""
from clinical_pre_mortem_agent.detectors import run_all_detectors
from clinical_pre_mortem_agent.edits import _verified, propose_edit
from clinical_pre_mortem_agent.models import CarePlan, Medication, PatientRecord
from clinical_pre_mortem_agent.ranking import rank_findings


def _plan(meds, egfr=85.0, weight=70.0, allergies=(), allergies_known=True,
          follow_up_days=30, monitoring_labs=(), instructions=()):
    patient = PatientRecord(patient_id="T-1", display_name="Mrs Test (synthetic)",
                            age_years=70, egfr=egfr, weight_kg=weight,
                            allergies=tuple(allergies), allergies_known=allergies_known)
    return CarePlan("T-1", patient, list(meds), follow_up_days=follow_up_days,
                    monitoring_labs=tuple(monitoring_labs),
                    instructions=tuple(instructions))


def test_ranking_is_severity_times_plausibility():
    plan = _plan([Medication("warfarin", 5, 1), Medication("ibuprofen", 400, 3, is_new=True)])
    ranked = rank_findings(run_all_detectors(plan))
    assert ranked[0].category == "drug_interaction"  # 4 x 1.0 = 4.0
    assert ranked[1].category == "unmonitored_lab"  # 3 x 0.8 = 2.4


def test_ranking_tie_breaks_are_deterministic():
    plan = _plan([Medication("warfarin", 5, 1), Medication("ibuprofen", 400, 3, is_new=True)])
    first = [f.category for f in rank_findings(run_all_detectors(plan))]
    second = [f.category for f in rank_findings(run_all_detectors(plan))]
    assert first == second


def test_allergy_edit_substitutes_and_is_valid():
    plan = _plan([Medication("amoxicillin", 500, 3, is_new=True)],
                 allergies=("penicillin",))
    finding = run_all_detectors(plan)[0]
    edit = propose_edit(plan, finding)
    assert edit is not None
    assert "azithromycin" in edit.action
    assert edit.is_valid


def test_allergy_edit_without_substitute_stops_the_drug():
    # Methotrexate has no substitute in the demo table; allergy to it
    # must still produce a valid edit (stop the drug).
    plan = _plan([Medication("methotrexate", 15, 1, is_new=True)],
                 allergies=("methotrexate",), monitoring_labs=("CBC", "ALT"))
    finding = run_all_detectors(plan)[0]
    edit = propose_edit(plan, finding)
    assert edit is not None
    assert "stop methotrexate" in edit.action
    assert edit.is_valid


def test_renal_contraindicated_edit_stops_drug():
    plan = _plan([Medication("metformin", 1000, 2)], egfr=25.0)
    finding = run_all_detectors(plan)[0]
    edit = propose_edit(plan, finding)
    assert edit is not None and "stop metformin" in edit.action
    assert edit.is_valid


def test_renal_dose_edit_reduces_to_limit():
    plan = _plan([Medication("gabapentin", 800, 3)], egfr=40.0)
    finding = run_all_detectors(plan)[0]
    edit = propose_edit(plan, finding)
    assert edit is not None and "reduce gabapentin" in edit.action
    assert edit.is_valid


def test_interaction_edit_holds_the_new_drug():
    plan = _plan([Medication("warfarin", 5, 1), Medication("ibuprofen", 400, 3, is_new=True)],
                 monitoring_labs=("INR",))
    finding = run_all_detectors(plan)[0]
    edit = propose_edit(plan, finding)
    assert edit is not None and "hold ibuprofen" in edit.action
    assert edit.is_valid


def test_follow_up_edit_schedules_in_time():
    plan = _plan([Medication("warfarin", 5, 1, is_new=True)],
                 follow_up_days=None, monitoring_labs=("INR",))
    finding = run_all_detectors(plan)[0]
    edit = propose_edit(plan, finding)
    assert edit is not None and "7 days" in edit.action
    assert edit.is_valid


def test_contradictory_dose_edit_keeps_one_dose():
    plan = _plan([Medication("amoxicillin", 500, 3), Medication("amoxicillin", 250, 3)])
    finding = run_all_detectors(plan)[0]
    edit = propose_edit(plan, finding)
    assert edit is not None and edit.is_valid


def test_unmonitored_lab_edit_orders_the_missing_lab():
    plan = _plan([Medication("warfarin", 5, 1, is_new=True)], follow_up_days=7)
    finding = run_all_detectors(plan)[0]
    edit = propose_edit(plan, finding)
    assert edit is not None and "INR" in edit.action
    assert edit.is_valid


def test_edit_that_introduces_a_new_failure_is_invalid():
    # An edit that fixes the interaction but adds a drug the patient is
    # allergic to must be reported invalid, not hidden.
    plan = _plan([Medication("warfarin", 5, 1), Medication("ibuprofen", 400, 3, is_new=True)],
                 allergies=("penicillin",), monitoring_labs=("INR",))
    finding = run_all_detectors(plan)[0]
    bad_edited = plan.copy_with(
        medications=[Medication("warfarin", 5, 1), Medication("amoxicillin", 500, 3)])
    edit = _verified(plan, bad_edited, finding, "swap ibuprofen -> amoxicillin",
                     "bad edit used in the test")
    assert edit.kills_failure is True
    assert edit.introduces_new_failure is True
    assert edit.is_valid is False
