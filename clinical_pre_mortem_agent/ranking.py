"""Ranking: severity x plausibility, highest risk first.

A pre-mortem produces several imagined failures; a clinician can only
act on a few. Findings are ranked by ``risk_score = severity x
plausibility`` so the most severe *and* best-supported failures come
first. Ties break toward the higher severity, then alphabetically by
category, so the order is fully deterministic.
"""
from __future__ import annotations

from .models import Finding


def rank_findings(findings: list[Finding]) -> list[Finding]:
    """Sort findings by risk score (desc), severity (desc), category (asc)."""
    return sorted(
        findings,
        key=lambda f: (-f.risk_score, -f.severity, f.category, f.drug),
    )
