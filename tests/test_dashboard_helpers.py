"""Tests for dashboard/helpers.py — plain Python, no Streamlit session needed.

The helpers are imported by file path (dashboard/ is deliberately not a
package): dashboard/ itself is added below so `import helpers` resolves
the same way it does in app.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))

import helpers  # noqa: E402
from clinical_pre_mortem_agent import sample_plan  # noqa: E402


def test_sample_plans_cover_faulty_clean_and_absent():
    plans = helpers.sample_plans()
    assert len(plans) == 5
    assert any("Demo" in name for name in plans)
    assert any("Clean" in name for name in plans)
    assert any("Evidence absent" in name for name in plans)


def test_run_plan_summary_matches_pipeline():
    summary = helpers.run_plan(sample_plan())
    assert summary["verdict"] == "RISKS FOUND"
    assert summary["findings"][0]["category"] == "drug_interaction"
    assert summary["findings"][0]["risk_score"] == 4.0
    assert summary["edits"][0]["is_valid"] is True
    assert "story" in summary["findings"][0]


def test_findings_table_rows():
    summary = helpers.run_plan(sample_plan())
    rows = helpers.findings_table(summary)
    assert len(rows) == 2
    assert rows[0]["Category"] == "drug_interaction"
    assert rows[0]["Risk"] == 4.0


def test_load_evaluation_returns_none_without_results(tmp_path):
    assert helpers.load_evaluation(tmp_path) is None


def test_load_evaluation_reads_saved_json(tmp_path):
    from clinical_pre_mortem_agent.evaluation import evaluate, write_results
    write_results(evaluate(), tmp_path)
    loaded = helpers.load_evaluation(tmp_path)
    assert loaded is not None
    assert loaded["failure_recall"] == 1.0
    assert loaded["n_cases"] == 42


def test_evaluation_metrics_runs_live():
    metrics = helpers.evaluation_metrics()
    assert metrics["failure_recall"] == 1.0
    assert metrics["false_alarm_rate"] == 0.0
