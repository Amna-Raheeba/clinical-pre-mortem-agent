"""Notebook 02: evaluation experiment — per-category recall, chain metrics,
and the honest-limit analysis.

Run from the repo root:

    python notebooks/02_evaluation_experiment.py

Prints failure recall per taxonomy category, the false-alarm rate on
clean plans, minimal-edit success, the abstention rate, and the three
chain metrics — then writes results/evaluation.json and
results/evaluation.csv. Used by CI.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clinical_pre_mortem_agent.evaluation import build_eval_dataset, evaluate, write_results
from clinical_pre_mortem_agent.pre_mortem import run_pre_mortem

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    cases = build_eval_dataset()
    metrics = evaluate(cases)
    write_results(metrics, ROOT / "results")

    # Per-category recall: how many injected faults of each kind were found.
    per_category: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for case in cases:
        if not case.injected:
            continue
        report = run_pre_mortem(case.plan)
        found = {f.category for f in report.findings}
        for category in case.injected:
            per_category[category][1] += 1
            if category in found:
                per_category[category][0] += 1

    print("Per-category failure recall (injected faults found / injected):")
    for category in sorted(per_category):
        found, total = per_category[category]
        print(f"  {category:28s} {found}/{total} = {found / total:.2f}")

    # False alarms by category on clean plans.
    false_alarms: Counter = Counter()
    for case in cases:
        if case.injected or case.expected_abstention is not None:
            continue
        report = run_pre_mortem(case.plan)
        for finding in report.findings:
            false_alarms[finding.category] += 1
    print(f"\nFalse alarms on clean plans: {dict(false_alarms) or 'none'}")

    print(f"\nOverall: recall {metrics['failure_recall']}, "
          f"false-alarm rate {metrics['false_alarm_rate']}, "
          f"minimal-edit success {metrics['minimal_edit_success']}, "
          f"abstention rate {metrics['abstention_rate']}")
    print(f"Chains: recall {metrics['chain_recall']} "
          f"({metrics['chains_found']}/{metrics['chains_expected']} expected found), "
          f"break rate {metrics['chain_break_rate']} "
          f"({metrics['chains_broken']}/{metrics['chains_detected']} broken by one edit), "
          f"false-chain rate {metrics['false_chain_rate']} "
          f"({metrics['clean_with_chains']}/{metrics['n_clean']} clean plans with a chain)")
    print("Results written to results/evaluation.json and results/evaluation.csv")


if __name__ == "__main__":
    main()
