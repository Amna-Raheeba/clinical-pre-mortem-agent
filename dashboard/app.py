"""Streamlit dashboard for the clinical pre-mortem agent.

Run it from the repo root:

    pip install streamlit
    streamlit run dashboard/app.py

Streamlit is a dashboard-only dependency — the core package
(``clinical_pre_mortem_agent``) stays standard-library only. Every number
on this page comes from a live run of the pipeline via
``dashboard/helpers.py``; nothing is hardcoded or screenshotted. All
patients are synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Streamlit puts this script's folder (dashboard/) on sys.path, not the repo
# root, so add both explicitly before importing the package or the helpers.
ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "dashboard")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st  # noqa: E402

import helpers  # noqa: E402

st.set_page_config(page_title="Clinical Pre-Mortem — Dashboard", layout="wide")
st.title("Clinical Pre-Mortem Agent")
st.caption(
    "Assume the care plan has already harmed the patient. Work backwards: "
    "name the failure, its earliest warning sign, and the one change that "
    "would have prevented it. Research prototype — synthetic plans only, "
    "not clinical guidance, not for use on real patients."
)

tab_plan, tab_eval = st.tabs(["Run a pre-mortem", "Evaluation"])

with tab_plan:
    plans = helpers.sample_plans()
    choice = st.sidebar.selectbox("Sample plan", list(plans.keys()))
    plan = plans[choice]
    st.subheader(f"Plan {plan.plan_id} — {plan.indication or 'no indication recorded'}")
    st.write(
        f"Patient: {plan.patient.display_name}, {plan.patient.age_years} years, "
        f"eGFR {plan.patient.egfr if plan.patient.egfr is not None else 'not recorded'}, "
        f"weight {plan.patient.weight_kg if plan.patient.weight_kg is not None else 'not recorded'} kg"
    )
    st.write("Medications: " + "; ".join(
        f"{m.name} {m.dose_mg:.0f} mg x {m.doses_per_day}/day"
        + (" (new)" if m.is_new else "")
        for m in plan.medications
    ))
    st.write(f"Follow-up: {plan.follow_up_days if plan.follow_up_days is not None else 'none scheduled'} days")
    st.write(f"Monitoring labs: {', '.join(plan.monitoring_labs) or 'none ordered'}")
    if plan.instructions:
        st.write("Instructions: " + "; ".join(plan.instructions))

    if st.button("Run pre-mortem"):
        summary = helpers.run_plan(plan)
        verdict = summary["verdict"]
        if verdict == "SAFE":
            st.success(f"Verdict: {verdict}")
        elif "ABSTAINED" in verdict:
            st.warning(f"Verdict: {verdict}")
        else:
            st.error(f"Verdict: {verdict}")

        if summary["findings"]:
            st.subheader("Ranked failures")
            st.dataframe(helpers.findings_table(summary), width="stretch")
            for finding in summary["findings"]:
                with st.expander(f"{finding['category']} — risk {finding['risk_score']}"):
                    st.write(f"**{finding['detail']}**")
                    st.write(f"Evidence: {'; '.join(finding['evidence'])}")
                    st.write(f"Earliest warning sign: {finding['earliest_warning_sign']}")
                    st.write(f"Story: {finding['story']}")
        if summary["edits"]:
            st.subheader("Minimal edits (verified)")
            for edit in summary["edits"]:
                mark = "VALID" if edit["is_valid"] else "INVALID"
                st.write(f"- [{mark}] **{edit['action']}** — {edit['description']}")
        if summary["chains"]:
            st.subheader("Failure chains — one failure enabling a second")
            st.dataframe(helpers.chains_table(summary), width="stretch")
            for chain_break in summary["chain_breaks"]:
                status = "BROKEN" if chain_break["chain_broken"] else "NOT BROKEN"
                st.write(f"- [{status}] **{chain_break['action']}** — breaks the "
                         f"{chain_break['enabler']} -> {chain_break['enabled']} chain "
                         f"by restoring the check that would have caught it. It does "
                         f"not fix the enabled failure itself; that still needs its "
                         f"own edit.")
        if summary["abstentions"]:
            st.subheader("Abstentions")
            for abstention in summary["abstentions"]:
                st.write(f"- {abstention['category']}: {abstention['reason']}")

with tab_eval:
    st.subheader("Seeded evaluation — 50 synthetic cases")
    st.write("24 faulty plans (4 per category), 8 chained plans (2 per link), "
             "12 clean plans, 6 evidence-absent plans. "
             "Run live on this page; nothing is cached from an old run.")
    if st.button("Run evaluation"):
        metrics = helpers.evaluation_metrics()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Failure recall",
                    f"{metrics['failure_recall']:.2f}",
                    f"{metrics['injected_found']}/{metrics['injected_total']} faults found")
        col2.metric("False-alarm rate",
                    f"{metrics['false_alarm_rate']:.2f}",
                    f"{metrics['clean_with_findings']}/{metrics['n_clean']} clean plans flagged")
        col3.metric("Minimal-edit success",
                    f"{metrics['minimal_edit_success']:.2f}",
                    f"{metrics['edits_valid']}/{metrics['edits_proposed']} edits valid")
        col4.metric("Abstention rate",
                    f"{metrics['abstention_rate']:.2f}",
                    f"{metrics['abstain_correct']}/{metrics['n_evidence_absent']} correct")
        col5, col6, col7 = st.columns(3)
        col5.metric("Chain recall",
                    f"{metrics['chain_recall']:.2f}",
                    f"{metrics['chains_found']}/{metrics['chains_expected']} expected chains found")
        col6.metric("Chain-break rate",
                    f"{metrics['chain_break_rate']:.2f}",
                    f"{metrics['chains_broken']}/{metrics['chains_detected']} chains broken by one edit")
        col7.metric("False-chain rate",
                    f"{metrics['false_chain_rate']:.2f}",
                    f"{metrics['clean_with_chains']}/{metrics['n_clean']} clean plans with a chain")
        st.write(
            "Honest limit: the faults are injected from the same knowledge "
            "base the detectors read, so recall measures consistency, not "
            "performance on faults invented by someone else. The "
            "false-alarm rate on genuinely safe plans is the more "
            "informative number. The same limit applies to the chains: "
            "they are defined over the deterministic taxonomy, not real "
            "clinical causality."
        )
    stored = helpers.load_evaluation(ROOT / "results")
    if stored is not None:
        st.write("Last saved run (results/evaluation.json):")
        st.json({k: v for k, v in stored.items()})
