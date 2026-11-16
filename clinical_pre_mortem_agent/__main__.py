"""Command-line interface for the clinical pre-mortem agent.

Usage (from the repo root):

    python -m clinical_pre_mortem_agent demo
        Run the pre-mortem on the built-in demo plan and print the report.

    python -m clinical_pre_mortem_agent check --plan examples/sample_plan.json
        Run the pre-mortem on a plan stored as JSON and print the report.

    python -m clinical_pre_mortem_agent evaluate [--out results]
        Run the seeded evaluation (42 synthetic cases) and write
        results/evaluation.json and results/evaluation.csv.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .evaluation import evaluate, sample_plan, write_results
from .plan_io import load_plan
from .pre_mortem import run_pre_mortem


def _print_report(report) -> None:
    print(f"Plan {report.plan_id}: {report.verdict}")
    print(f"Findings: {len(report.findings)}  "
          f"Edits proposed: {len(report.edits)}  "
          f"Abstentions: {len(report.abstentions)}")
    for finding in report.ranked_findings:
        print(f"\n[{finding.category}] risk {finding.risk_score:.2f} "
              f"(severity {finding.severity}, plausibility {finding.plausibility})")
        print(f"  {finding.detail}")
        print(f"  Evidence: {'; '.join(finding.evidence)}")
        print(f"  Earliest warning sign: {finding.earliest_warning_sign}")
        print(f"  Story: {report.stories[finding.category]}")
    for edit in report.edits:
        status = "VALID" if edit.is_valid else "INVALID"
        print(f"\n  Edit [{status}]: {edit.action}")
        print(f"    {edit.description} (kills failure: {edit.kills_failure}, "
              f"new failure: {edit.introduces_new_failure})")
    for abstention in report.abstentions:
        print(f"\n  Abstained on {abstention.category}: {abstention.reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="clinical-pre-mortem-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("demo", help="run the pre-mortem on the built-in demo plan")
    check = sub.add_parser("check", help="run the pre-mortem on a JSON plan file")
    check.add_argument("--plan", required=True, help="path to a plan JSON file")
    evaluate_parser = sub.add_parser("evaluate", help="run the seeded evaluation")
    evaluate_parser.add_argument("--out", default="results",
                                 help="output directory (default: results)")

    args = parser.parse_args(argv)

    if args.command == "demo":
        _print_report(run_pre_mortem(sample_plan()))
        return 0
    if args.command == "check":
        _print_report(run_pre_mortem(load_plan(Path(args.plan))))
        return 0
    if args.command == "evaluate":
        metrics = evaluate()
        write_results(metrics, Path(args.out))
        print(f"cases: {metrics['n_cases']} "
              f"(faulty {metrics['n_faulty']}, clean {metrics['n_clean']}, "
              f"evidence-absent {metrics['n_evidence_absent']})")
        print(f"failure_recall: {metrics['failure_recall']} "
              f"({metrics['injected_found']}/{metrics['injected_total']})")
        print(f"false_alarm_rate: {metrics['false_alarm_rate']} "
              f"({metrics['clean_with_findings']}/{metrics['n_clean']} clean plans flagged)")
        print(f"minimal_edit_success: {metrics['minimal_edit_success']} "
              f"({metrics['edits_valid']}/{metrics['edits_proposed']} edits valid)")
        print(f"abstention_rate: {metrics['abstention_rate']} "
              f"({metrics['abstain_correct']}/{metrics['n_evidence_absent']})")
        print(f"wrote {args.out}/evaluation.json and {args.out}/evaluation.csv")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
