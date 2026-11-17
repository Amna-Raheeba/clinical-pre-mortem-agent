"""Second-order failure chains: when one failure enables a second.

A pre-mortem that lists failures one by one misses the way they hide
each other. A renal dose error is bad; a renal dose error *with no
monitoring lab ordered* is worse, because the test that would have
revealed the drug accumulating was never ordered. A warfarin
interaction is bad; with no follow-up visit scheduled, nobody is ever
going to notice the INR drifting.

A chain is two findings where the first *enables* the second: the
enabler removes the check that would have caught the enabled failure.
The link table lives in :mod:`knowledge` (``CHAIN_LINKS``) and is a
statement about this deterministic taxonomy — "enables" means "removes
the check that would have caught it", which is exactly what the rule
engine can see. It is not a claim about real clinical causality.

A chain exists when:
1. the (enabler category, enabled category) pair is in the link table, and
2. the two findings share a drug — the hiding must be about the same
   drug, not a coincidence on the same plan.

Breaking a chain takes one edit, and it targets the enabler: apply the
enabler's minimal edit (order the missing lab, schedule the missed
visit) and re-run chain detection on the edited plan. The chain is
broken only when the edit is verified valid AND no chain remains.
Breaking the chain restores detection — it does NOT fix the enabled
failure itself, which still needs its own edit, and the report says so.
"""
from __future__ import annotations

from . import knowledge as kb
from .detectors import run_all_detectors
from .edits import propose_edit_with_plan
from .models import CarePlan, ChainBreak, FailureChain, Finding


def _drug_set(drug_field: str) -> set[str]:
    """The drugs a finding concerns: split "a + b" into {"a", "b"}."""
    return {part.strip().lower() for part in drug_field.split("+") if part.strip()}


def detect_chains(findings: list[Finding]) -> list[FailureChain]:
    """Detect second-order chains among a plan's findings.

    Each ordered pair of distinct findings is checked against the link
    table and the shared-drug condition. A finding never chains with
    itself, and each ordered pair is reported once.
    """
    links = {(a, b): text for a, b, text in kb.CHAIN_LINKS}
    chains: list[FailureChain] = []
    for enabler in findings:
        for enabled in findings:
            if enabler is enabled:
                continue
            text = links.get((enabler.category, enabled.category))
            if text is None:
                continue
            if not _drug_set(enabler.drug) & _drug_set(enabled.drug):
                continue
            chains.append(FailureChain(enabler=enabler, enabled=enabled, link=text))
    return chains


def break_chain(plan: CarePlan, chain: FailureChain) -> ChainBreak | None:
    """Compute the single edit that breaks a chain, verified.

    The break targets the enabler: its minimal edit is applied to a
    copy of the plan, and chain detection is re-run on the edited plan.
    Returns None when the enabler has no edit. ``chain_broken`` is True
    only when the edit is verified valid and no chain remains at all.
    """
    edit, edited = propose_edit_with_plan(plan, chain.enabler)
    if edit is None or edited is None:
        return None
    remaining = detect_chains(run_all_detectors(edited))
    return ChainBreak(
        chain=chain,
        edit=edit,
        chain_broken=edit.is_valid and len(remaining) == 0,
    )
