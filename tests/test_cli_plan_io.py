"""Tests for plan JSON round-trips and the CLI."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from clinical_pre_mortem_agent import sample_plan
from clinical_pre_mortem_agent.__main__ import main
from clinical_pre_mortem_agent.plan_io import plan_from_dict, plan_to_dict


def test_plan_json_round_trip_preserves_missing_egfr(tmp_path):
    plan = sample_plan()
    plan = plan.copy_with(patient=plan.patient)
    data = plan_to_dict(plan)
    restored = plan_from_dict(json.loads(json.dumps(data)))
    assert restored.patient.egfr == plan.patient.egfr
    assert restored.medications[0].name == plan.medications[0].name
    assert restored.follow_up_days == plan.follow_up_days


def test_plan_json_round_trip_keeps_none_egfr_none():
    from clinical_pre_mortem_agent.models import CarePlan, Medication, PatientRecord
    patient = PatientRecord(patient_id="T-1", display_name="Mrs Test (synthetic)",
                            age_years=70, egfr=None, weight_kg=None)
    plan = CarePlan("T-1", patient, [Medication("metformin", 500, 2)])
    restored = plan_from_dict(json.loads(json.dumps(plan_to_dict(plan))))
    assert restored.patient.egfr is None
    assert restored.patient.weight_kg is None


def test_cli_demo_exits_zero_and_names_verdict(capsys):
    assert main(["demo"]) == 0
    assert "RISKS FOUND" in capsys.readouterr().out


def test_cli_check_reads_a_json_plan(tmp_path, capsys):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan_to_dict(sample_plan())))
    assert main(["check", "--plan", str(path)]) == 0
    assert "DEMO-1" in capsys.readouterr().out


def test_cli_evaluate_writes_results(tmp_path, capsys):
    out = tmp_path / "results"
    assert main(["evaluate", "--out", str(out)]) == 0
    assert (out / "evaluation.json").exists()
    assert (out / "evaluation.csv").exists()
    assert "failure_recall: 1.0" in capsys.readouterr().out


def test_cli_runs_as_module():
    result = subprocess.run(
        [sys.executable, "-m", "clinical_pre_mortem_agent", "demo"],
        capture_output=True, text=True, cwd=str(ROOT))
    assert result.returncode == 0
    assert "RISKS FOUND" in result.stdout
