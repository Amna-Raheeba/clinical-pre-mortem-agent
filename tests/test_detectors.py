"""Tests for the six deterministic detectors."""
from clinical_pre_mortem_agent.detectors import run_all_detectors
from clinical_pre_mortem_agent.models import CarePlan, Medication, PatientRecord


def _plan(meds, egfr=85.0, weight=70.0, allergies=(), allergies_known=True,
          follow_up_days=30, monitoring_labs=(), instructions=()):
    patient = PatientRecord(patient_id="T-1", display_name="Mrs Test (synthetic)",
                            age_years=70, egfr=egfr, weight_kg=weight,
                            allergies=tuple(allergies), allergies_known=allergies_known)
    return CarePlan("T-1", patient, list(meds), follow_up_days=follow_up_days,
                    monitoring_labs=tuple(monitoring_labs),
                    instructions=tuple(instructions))


def _cats(plan):
    return {f.category for f in run_all_detectors(plan)}


# ------------------------------------------------------------ missed allergy
def test_allergy_exact_match_fires():
    plan = _plan([Medication("amoxicillin", 500, 3)], allergies=("amoxicillin",))
    findings = run_all_detectors(plan)
    assert len(findings) == 1
    assert findings[0].category == "missed_allergy"
    assert findings[0].severity == 5
    assert findings[0].plausibility == 1.0


def test_allergy_class_match_fires_with_lower_plausibility():
    plan = _plan([Medication("amoxicillin", 500, 3)], allergies=("penicillin",))
    findings = run_all_detectors(plan)
    assert len(findings) == 1
    assert findings[0].plausibility == 0.85


def test_no_allergy_no_finding():
    assert _cats(_plan([Medication("amoxicillin", 500, 3)])) == set()


def test_allergy_unknown_is_silent_for_detector():
    # The abstention module owns this case; the detector must not guess.
    plan = _plan([Medication("amoxicillin", 500, 3)], allergies_known=False)
    assert _cats(plan) == set()


# ------------------------------------------------------------ renal dose error
def test_metformin_contraindicated_below_egfr_30():
    plan = _plan([Medication("metformin", 1000, 2)], egfr=25.0)
    findings = run_all_detectors(plan)
    assert len(findings) == 1
    assert "contraindicated" in findings[0].detail


def test_metformin_reduced_limit_in_egfr_band():
    plan = _plan([Medication("metformin", 1000, 2)], egfr=40.0)
    assert _cats(plan) == {"renal_dose_error"}
    plan_ok = _plan([Medication("metformin", 500, 2)], egfr=40.0)
    assert _cats(plan_ok) == set()


def test_gentamicin_weight_based_limit():
    # follow_up_days=3: gentamicin levels must be reviewed within 3 days,
    # so the follow-up rule must not fire a second, unintended fault here.
    plan = _plan([Medication("gentamicin", 240, 2, is_new=True)], egfr=50.0, weight=60.0,
                 follow_up_days=3, monitoring_labs=("creatinine", "gentamicin level"))
    assert _cats(plan) == {"renal_dose_error"}


def test_gentamicin_safe_dose_passes():
    plan = _plan([Medication("gentamicin", 120, 2, is_new=True)], egfr=50.0, weight=70.0,
                 follow_up_days=3, monitoring_labs=("creatinine", "gentamicin level"))
    assert _cats(plan) == set()


def test_renal_detector_silent_without_egfr():
    plan = _plan([Medication("metformin", 1000, 2)], egfr=None)
    assert _cats(plan) == set()


# ------------------------------------------------------------ drug interaction
def test_warfarin_nsaid_interaction():
    plan = _plan([Medication("warfarin", 5, 1), Medication("ibuprofen", 400, 3, is_new=True)],
                 monitoring_labs=("INR",))
    findings = run_all_detectors(plan)
    assert len(findings) == 1
    assert findings[0].category == "drug_interaction"
    assert findings[0].plausibility == 1.0  # one drug newly started


def test_interaction_without_new_drug_is_slightly_less_plausible():
    plan = _plan([Medication("warfarin", 5, 1), Medication("ibuprofen", 400, 3)],
                 monitoring_labs=("INR",))
    findings = run_all_detectors(plan)
    assert findings[0].plausibility == 0.9


def test_no_interaction_for_unrelated_pair():
    plan = _plan([Medication("warfarin", 5, 1), Medication("paracetamol", 1000, 4)],
                 monitoring_labs=("INR",))
    assert _cats(plan) == set()


# ------------------------------------------------------------ missing follow-up
def test_new_warfarin_without_follow_up():
    plan = _plan([Medication("warfarin", 5, 1, is_new=True)],
                 follow_up_days=None, monitoring_labs=("INR",))
    assert _cats(plan) == {"missing_follow_up"}


def test_late_follow_up_fires():
    plan = _plan([Medication("warfarin", 5, 1, is_new=True)],
                 follow_up_days=30, monitoring_labs=("INR",))
    assert _cats(plan) == {"missing_follow_up"}


def test_timely_follow_up_passes():
    plan = _plan([Medication("warfarin", 5, 1, is_new=True)],
                 follow_up_days=7, monitoring_labs=("INR",))
    assert _cats(plan) == set()


def test_continued_drug_needs_no_follow_up():
    plan = _plan([Medication("warfarin", 5, 1)], follow_up_days=None,
                 monitoring_labs=("INR",))
    assert _cats(plan) == set()


# ------------------------------------------------------- contradictory instruction
def test_same_drug_two_doses():
    plan = _plan([Medication("amoxicillin", 500, 3), Medication("amoxicillin", 250, 3)])
    assert _cats(plan) == {"contradictory_instruction"}


def test_duplicate_nsaid_therapy():
    plan = _plan([Medication("ibuprofen", 400, 3), Medication("naproxen", 500, 2)])
    assert _cats(plan) == {"contradictory_instruction"}


def test_written_instructions_contradict_each_other():
    plan = _plan([Medication("paracetamol", 1000, 4)],
                 instructions=("take with food", "take on an empty stomach"))
    assert _cats(plan) == {"contradictory_instruction"}


def test_instruction_against_drug_standard():
    plan = _plan([Medication("ibuprofen", 400, 3)],
                 instructions=("take on an empty stomach",))
    assert _cats(plan) == {"contradictory_instruction"}


def test_correct_instruction_passes():
    plan = _plan([Medication("ibuprofen", 400, 3)], instructions=("take with food",))
    assert _cats(plan) == set()


def test_one_fault_is_never_reported_twice():
    # Both instructions contradict AND one contradicts the drug standard:
    # still exactly one finding.
    plan = _plan([Medication("levothyroxine", 100, 1)],
                 instructions=("take with food", "take on an empty stomach"))
    findings = run_all_detectors(plan)
    assert len(findings) == 1


# ------------------------------------------------------------ unmonitored lab
def test_warfarin_without_inr():
    plan = _plan([Medication("warfarin", 5, 1, is_new=True)], follow_up_days=7)
    assert _cats(plan) == {"unmonitored_lab"}


def test_partial_monitoring_still_fires():
    plan = _plan([Medication("lisinopril", 10, 1, is_new=True)],
                 monitoring_labs=("creatinine",))
    assert _cats(plan) == {"unmonitored_lab"}


def test_full_monitoring_passes():
    plan = _plan([Medication("lisinopril", 10, 1, is_new=True)],
                 monitoring_labs=("potassium", "creatinine"))
    assert _cats(plan) == set()
