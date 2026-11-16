"""Tests for abstention and for the storytellers."""
import pytest

from clinical_pre_mortem_agent.abstention import check_abstentions
from clinical_pre_mortem_agent.models import CarePlan, Medication, PatientRecord
from clinical_pre_mortem_agent.stories import LLMStoryteller, MockStoryteller, StorytellerUnavailable


def _plan(meds, egfr=85.0, weight=70.0, allergies_known=True):
    patient = PatientRecord(patient_id="T-1", display_name="Mrs Test (synthetic)",
                            age_years=70, egfr=egfr, weight_kg=weight,
                            allergies_known=allergies_known)
    return CarePlan("T-1", patient, list(meds))


def test_abstain_allergy_when_history_unknown():
    plan = _plan([Medication("amoxicillin", 500, 3)], allergies_known=False)
    abstentions = check_abstentions(plan)
    assert len(abstentions) == 1
    assert abstentions[0].category == "missed_allergy"
    assert "allergy history" in abstentions[0].reason


def test_abstain_renal_when_egfr_missing():
    plan = _plan([Medication("metformin", 1000, 2)], egfr=None)
    abstentions = check_abstentions(plan)
    assert any(a.category == "renal_dose_error" for a in abstentions)


def test_abstain_renal_when_weight_missing_for_gentamicin():
    plan = _plan([Medication("gentamicin", 240, 2)], weight=None)
    abstentions = check_abstentions(plan)
    assert any(a.category == "renal_dose_error" for a in abstentions)
    assert "weight" in abstentions[0].reason


def test_no_abstention_when_evidence_present():
    plan = _plan([Medication("metformin", 500, 2)])
    assert check_abstentions(plan) == []


def test_no_renal_abstention_when_no_renal_drug():
    plan = _plan([Medication("paracetamol", 1000, 4)], egfr=None)
    assert check_abstentions(plan) == []


def test_mock_storyteller_names_patient_drug_and_sign():
    from clinical_pre_mortem_agent import run_pre_mortem, sample_plan
    plan = sample_plan()
    report = run_pre_mortem(plan)
    story = report.stories["drug_interaction"]
    assert "Mrs Demo" in story
    assert "ibuprofen + warfarin" in story
    assert "bruising" in story


def test_mock_storyteller_is_deterministic():
    from clinical_pre_mortem_agent import run_pre_mortem, sample_plan
    plan = sample_plan()
    first = run_pre_mortem(plan).stories
    second = run_pre_mortem(plan).stories
    assert first == second


def test_llm_storyteller_without_backend_raises():
    from clinical_pre_mortem_agent import run_pre_mortem, sample_plan
    plan = sample_plan()
    report = run_pre_mortem(plan)
    finding = report.ranked_findings[0]
    with pytest.raises(StorytellerUnavailable):
        LLMStoryteller().tell(plan, finding)


def test_llm_storyteller_with_fake_backend_uses_it():
    from clinical_pre_mortem_agent import run_pre_mortem, sample_plan
    plan = sample_plan()
    report = run_pre_mortem(plan)
    finding = report.ranked_findings[0]
    storyteller = LLMStoryteller(generate=lambda prompt: "FAKE STORY: " + prompt[:10])
    assert storyteller.tell(plan, finding).startswith("FAKE STORY")


def test_story_never_adds_a_finding():
    # Stories are generated from findings only; the count cannot grow.
    from clinical_pre_mortem_agent import run_pre_mortem, sample_plan
    report = run_pre_mortem(sample_plan())
    assert set(report.stories) == {f.category for f in report.findings}
