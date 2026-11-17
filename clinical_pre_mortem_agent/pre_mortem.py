"""The pre-mortem orchestrator: assume harm, work backwards, propose the fix.

One call reviews a whole plan:

1. **Abstain first** — name the categories that cannot be judged because
   evidence is absent, so "no failure found" is never a guess.
2. **Detect** — run the six deterministic detectors.
3. **Rank** — severity x plausibility, highest risk first.
4. **Imagine** — for the top failures, write the failure story (prose
   only; the story never changes the verdict).
5. **Edit** — for the top two failures, compute the minimal plan edit
   that kills the failure, verified by re-running the detectors.
6. **Chain** — detect second-order failure chains (one failure enabling
   a second) and, for each, the single edit that breaks the chain,
   verified by re-running chain detection on the edited plan.

The verdict is code: ``SAFE`` (no findings, no abstentions),
``RISKS FOUND`` (findings, no abstentions), ``ABSTAINED`` (no findings,
but some categories could not be judged), or both.
"""
from __future__ import annotations

from .abstention import check_abstentions
from .chains import break_chain, detect_chains
from .detectors import run_all_detectors
from .edits import propose_edit
from .models import CarePlan, PreMortemReport
from .ranking import rank_findings
from .stories import MockStoryteller

TOP_EDITS = 2  # minimal edits are computed for the top N ranked failures


def run_pre_mortem(plan: CarePlan, storyteller=None) -> PreMortemReport:
    """Review one care plan and return the full pre-mortem report."""
    if storyteller is None:
        storyteller = MockStoryteller()

    abstentions = check_abstentions(plan)
    findings = run_all_detectors(plan)
    ranked = rank_findings(findings)

    stories = {}
    for finding in ranked:
        stories[finding.category] = storyteller.tell(plan, finding)

    edits = []
    for finding in ranked[:TOP_EDITS]:
        edit = propose_edit(plan, finding)
        if edit is not None:
            edits.append(edit)

    chains = detect_chains(findings)
    chain_breaks = []
    for chain in chains:
        chain_break = break_chain(plan, chain)
        if chain_break is not None:
            chain_breaks.append(chain_break)

    if findings and abstentions:
        verdict = "RISKS FOUND + ABSTAINED"
    elif findings:
        verdict = "RISKS FOUND"
    elif abstentions:
        verdict = "ABSTAINED"
    else:
        verdict = "SAFE"

    return PreMortemReport(
        plan_id=plan.plan_id,
        findings=findings,
        ranked_findings=ranked,
        stories=stories,
        edits=edits,
        abstentions=abstentions,
        verdict=verdict,
        chains=chains,
        chain_breaks=chain_breaks,
    )
