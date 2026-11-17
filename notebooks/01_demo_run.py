"""Notebook 01: run the pre-mortem on the demo plan and print the report.

Run from the repo root:

    python notebooks/01_demo_run.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clinical_pre_mortem_agent import run_pre_mortem, sample_plan

if __name__ == "__main__":
    report = run_pre_mortem(sample_plan())
    print(f"Plan {report.plan_id}: {report.verdict}\n")
    for finding in report.ranked_findings:
        print(f"[{finding.category}] risk {finding.risk_score:.2f}")
        print(f"  {finding.detail}")
        print(f"  Story: {report.stories[finding.category]}\n")
    for edit in report.edits:
        print(f"Edit [{'VALID' if edit.is_valid else 'INVALID'}]: {edit.action}")
        print(f"  {edit.description}\n")
