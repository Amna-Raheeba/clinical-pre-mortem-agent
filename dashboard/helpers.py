"""Dashboard helpers — no Streamlit import here, so tests can import this
module in a bare environment. Every number comes from a live run of the
pre-mortem pipeline; nothing is hardcoded.
"""
from __future__ import annotations

import json
from pathlib import Path

from clinical_pre_mortem_agent.evaluation import build_eval_dataset, evaluate, sample_plan
from clinical_pre_mortem_agent.models import CarePlan
from clinical_pre_mortem_agent.pre_mortem import run_pre_mortem


def sample_plans() -> dict[str, CarePlan]:
    """Named demo plans for the dashboard sidebar."""
    plans = {"Demo: warfarin + new NSAID (2 risks)": sample_plan()}
    cases = build_eval_dataset()
    by_id = {case.plan.plan_id: case.plan for case in cases}
    plans["Faulty: penicillin allergy + amoxicillin"] = by_id["FA-1"]
    plans["Faulty: metformin at eGFR 25"] = by_id["FR-1"]
    plans["Clean: lisinopril, monitored"] = by_id["C-03"]
    plans["Evidence absent: eGFR missing"] = by_id["E-1"]
    return plans


def run_plan(plan: CarePlan) -> dict:
    """Run the pre-mortem and return a JSON-safe summary for display."""
    report = run_pre_mortem(plan)
    return {
        "plan_id": report.plan_id,
        "verdict": report.verdict,
        "findings": [
            {
                "category": f.category,
                "drug": f.drug,
                "detail": f.detail,
                "evidence": list(f.evidence),
                "severity": f.severity,
                "plausibility": f.plausibility,
                "risk_score": round(f.risk_score, 2),
                "earliest_warning_sign": f.earliest_warning_sign,
                "story": report.stories[f.category],
            }
            for f in report.ranked_findings
        ],
        "edits": [
            {
                "target_category": e.target_category,
                "drug": e.drug,
                "action": e.action,
                "description": e.description,
                "is_valid": e.is_valid,
            }
            for e in report.edits
        ],
        "abstentions": [
            {"category": a.category, "reason": a.reason}
            for a in report.abstentions
        ],
        "chains": [
            {
                "enabler": c.enabler.category,
                "enabled": c.enabled.category,
                "drug": c.enabled.drug,
                "link": c.link,
                "depth": c.depth,
                "risk_score": round(c.risk_score, 2),
            }
            for c in report.chains
        ],
        "chain_breaks": [
            {
                "enabler": b.chain.enabler.category,
                "enabled": b.chain.enabled.category,
                "action": b.edit.action,
                "description": b.edit.description,
                "chain_broken": b.chain_broken,
                "is_valid": b.edit.is_valid,
            }
            for b in report.chain_breaks
        ],
    }


def findings_table(summary: dict) -> list[dict]:
    """Rows for the findings table: one row per ranked finding."""
    return [
        {
            "Category": f["category"],
            "Drug": f["drug"],
            "Severity": f["severity"],
            "Plausibility": f["plausibility"],
            "Risk": f["risk_score"],
            "Detail": f["detail"],
        }
        for f in summary["findings"]
    ]


def chains_table(summary: dict) -> list[dict]:
    """Rows for the chains table: one row per second-order chain."""
    return [
        {
            "Enabler": c["enabler"],
            "Enabled": c["enabled"],
            "Drug": c["drug"],
            "Depth": c["depth"],
            "Chain risk": c["risk_score"],
            "Why it hides it": c["link"],
        }
        for c in summary["chains"]
    ]


def load_evaluation(results_dir: str | Path) -> dict | None:
    """Load results/evaluation.json if it exists, else None."""
    path = Path(results_dir) / "evaluation.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def evaluation_metrics() -> dict:
    """Run the live evaluation and return the summary metrics (no rows)."""
    metrics = evaluate()
    return {k: v for k, v in metrics.items() if k != "rows"}
