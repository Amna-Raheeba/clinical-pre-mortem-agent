"""Tests for second-order failure chains (chains.py).

A chain is two findings where the first *enables* the second: the
enabler removes the check that would have caught the enabled failure.
A chain exists only when the (enabler, enabled) category pair is in
the link table AND the two findings share a drug.
"""
from pathlib import Path

from clinical_pre_mortem_agent import (
    break_chain,
    detect_chains,
    run_pre_mortem,
    sample_plan,
)
from clinical_pre_mortem_agent.chains import _drug_set
from clinical_pre_mortem_agent.detectors import run_all_detectors
from clinical_pre_mortem_agent.edits import propose_edit_with_plan
from clinical_pre_mortem_agent.evaluation import (
    build_eval_dataset,
    evaluate,
    load_eval_cases,
)
from clinical_pre_mortem_agent.models import (
    CarePlan,
    FailureChain,
    Finding,
    Medication,
    PatientRecord,
)
from clinical_pre_mortem_agent.taxonomy import CATEGORIES


def _plan(meds, egfr=85.0, weight=70.0, follow_up_days=30,
          monitoring_labs=(), instructions=()):
    patient = PatientRecord(patient_id="T-1", display_name="Mrs Test (synthetic)",
                            age_years=70, egfr=egfr, weight_kg=weight)
    return CarePlan("T-1", patient, list(meds), follow_up_days=follow_up_days,
                    monitoring_labs=tuple(monitoring_labs),
                    instructions=tuple(instructions))


# ------------------------------------------------------------ link table
def test_chain_links_use_only_taxonomy_categories():
    from clinical_pre_mortem_agent import knowledge
    for enabler, enabled, _link in knowledge.CHAIN_LINKS:
        assert enabler in CATEGORIES
        assert enabled in CATEGORIES
        assert enabler != enabled


def test_drug_set_splits_interaction_pairs():
    assert _drug_set("warfarin + ibuprofen") == {"warfarin", "ibuprofen"}
    assert _drug_set("warfarin") == {"warfarin"}
    assert _drug_set("") == set()


# ------------------------------------------------------------ demo plan
def test_demo_plan_has_exactly_one_chain():
    report = run_pre_mortem(sample_plan())
    assert len(report.chains) == 1
    chain = report.chains[0]
    assert chain.enabler.category == "unmonitored_lab"
    assert chain.enabled.category == "drug_interaction"
    assert chain.depth == 2
    # Chain risk is the sum: unmonitored_lab 2.4 + interaction 4.0.
    assert chain.risk_score == 2.4 + 4.0
    assert "INR" in chain.link or "lab" in chain.link


def test_demo_chain_break_is_valid_and_verified():
    report = run_pre_mortem(sample_plan())
    assert len(report.chain_breaks) == 1
    chain_break = report.chain_breaks[0]
    assert chain_break.chain_broken is True
    assert chain_break.edit.is_valid is True
    assert chain_break.edit.action == "order monitoring labs: INR"


def test_breaking_a_chain_does_not_fix_the_enabled_failure():
    # Honest behaviour: ordering the lab restores detection, it does not
    # fix the interaction. After the break edit the interaction still
    # fires, the unmonitored lab does not, and no chain remains.
    report = run_pre_mortem(sample_plan())
    chain = report.chains[0]
    _edit, edited = propose_edit_with_plan(sample_plan(), chain.enabler)
    after = run_all_detectors(edited)
    assert {f.category for f in after} == {"drug_interaction"}
    assert detect_chains(after) == []


# ------------------------------------------------------------ conditions
def test_no_chain_without_a_shared_drug():
    # Gentamicin renal error + warfarin unmonitored lab: the hiding is
    # about a different drug, so there is no chain. (Gentamicin labs are
    # ordered, so the unmonitored-lab finding is warfarin's alone.)
    plan = _plan([Medication("gentamicin", 240, 2, is_new=True),
                  Medication("warfarin", 5, 1)],
                 egfr=50.0, weight=60.0, follow_up_days=3,
                 monitoring_labs=("creatinine", "gentamicin level"))
    findings = run_all_detectors(plan)
    assert {f.category for f in findings} == {"renal_dose_error", "unmonitored_lab"}
    assert {f.drug for f in findings} == {"gentamicin", "warfarin"}
    assert detect_chains(findings) == []


def test_no_chain_with_a_single_finding():
    plan = _plan([Medication("warfarin", 5, 1),
                  Medication("ibuprofen", 400, 3, is_new=True)],
                 monitoring_labs=("INR",), follow_up_days=7)
    findings = run_all_detectors(plan)
    assert [f.category for f in findings] == ["drug_interaction"]
    assert detect_chains(findings) == []


def test_chain_detection_is_deterministic():
    plan = sample_plan()
    first = detect_chains(run_all_detectors(plan))
    second = detect_chains(run_all_detectors(plan))
    assert [(c.enabler.category, c.enabled.category) for c in first] == \
           [(c.enabler.category, c.enabled.category) for c in second]


def test_break_chain_returns_none_when_the_enabler_has_no_edit():
    plan = _plan([Medication("paracetamol", 1000, 4)])
    fake_enabler = Finding(category="contradictory_instruction", drug="",
                           detail="no fault", evidence=(), severity=2,
                           plausibility=0.9)
    fake_enabled = Finding(category="renal_dose_error", drug="metformin",
                           detail="no fault", evidence=(), severity=4,
                           plausibility=0.9)
    chain = FailureChain(enabler=fake_enabler, enabled=fake_enabled,
                         link="test link")
    assert break_chain(plan, chain) is None


# ------------------------------------------------------------ seeded cases
def test_all_seeded_chained_cases_detect_exactly_their_chain():
    cases = {c.plan.plan_id: c for c in build_eval_dataset()}
    for pid in ("CH-1", "CH-2", "CH-3", "CH-4", "CH-5", "CH-6", "CH-7", "CH-8"):
        case = cases[pid]
        report = run_pre_mortem(case.plan)
        got = {(c.enabler.category, c.enabled.category) for c in report.chains}
        assert got == set(case.expected_chains), pid
        assert len(report.chains) == 1, pid
        assert all(b.chain_broken for b in report.chain_breaks), pid


def test_no_chains_anywhere_else_in_the_dataset():
    cases = build_eval_dataset()
    for case in cases:
        if case.expected_chains:
            continue
        report = run_pre_mortem(case.plan)
        assert report.chains == [], case.plan.plan_id


def test_report_serialises_chains_and_breaks():
    report = run_pre_mortem(sample_plan())
    data = report.to_dict()
    assert data["chains"] == [{
        "enabler": "unmonitored_lab",
        "enabled": "drug_interaction",
        "drug": "ibuprofen + warfarin",
        "link": report.chains[0].link,
        "depth": 2,
        "risk_score": 6.4,
    }]
    assert data["chain_breaks"] == [{
        "enabler": "unmonitored_lab",
        "enabled": "drug_interaction",
        "action": "order monitoring labs: INR",
        "chain_broken": True,
        "edit_valid": True,
    }]


# ------------------------------------------------------------ dataset JSON
def test_eval_plans_json_matches_the_code_dataset():
    root = Path(__file__).resolve().parent.parent
    loaded = load_eval_cases(root / "data" / "eval_plans.json")
    built = build_eval_dataset()
    assert len(loaded) == len(built) == 50
    for from_json, from_code in zip(loaded, built):
        assert from_json.plan == from_code.plan
        assert from_json.injected == from_code.injected
        assert from_json.expected_abstention == from_code.expected_abstention
        assert from_json.expected_chains == from_code.expected_chains


def test_chain_metrics_are_measured():
    metrics = evaluate()
    assert metrics["n_chained"] == 8
    assert metrics["chain_recall"] == 1.0
    assert metrics["chain_break_rate"] == 1.0
    assert metrics["false_chain_rate"] == 0.0
