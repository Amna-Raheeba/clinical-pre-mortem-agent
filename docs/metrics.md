# Metrics

All seven metrics are measured on the seeded synthetic dataset
(`data/eval_plans.json`, 50 cases: 24 faulty, 8 chained, 12 clean, 6
evidence-absent). Run it yourself:

```
python -m clinical_pre_mortem_agent evaluate
```

## 1. Failure recall — 1.00 (40/40)

Injected faults the detectors found, divided by injected faults.
Per category: 4/4 in every category (missed allergy, renal dose error,
drug interaction, missing follow-up, contradictory instruction,
unmonitored lab) — 8/8 for the four categories the chained cases
touch.

## 2. False-alarm rate — 0.00 (0/12)

Clean plans with at least one finding, divided by clean plans. Zero
false alarms on the 12 clean plans.

## 3. Minimal-edit success — 1.00 (40/40)

Top-ranked failures whose proposed edit is verified — the edit kills
the failure when the detectors are re-run, and introduces no new
failure — divided by edits proposed.

## 4. Abstention rate — 1.00 (6/6)

Evidence-absent plans where the agent abstained on the right category,
divided by evidence-absent plans. Missing eGFR with a renally dosed
drug, missing weight with gentamicin, and unknown allergy history all
abstain correctly.

## 5. Chain recall — 1.00 (8/8)

Expected second-order chains the chain detector found, divided by
expected chains. Two seeded cases per link, all four links.

## 6. Chain-break rate — 1.00 (8/8)

Detected chains broken by one verified edit — the enabler's edit is
valid and chain detection on the edited plan finds no chain —
divided by detected chains.

## 7. False-chain rate — 0.00 (0/12)

Clean plans with at least one chain, divided by clean plans. No clean
plan produces a chain: with no findings, there is nothing to chain.

## 8. What the numbers do and do not mean

The faults are injected from the same knowledge base the detectors
read, so failure recall measures **consistency** between the generator
and the detectors — not how the agent would do on faults invented by
someone else, or on real prescribing data. That is the honest limit,
and it is stated in the README and the experiment log.

The more informative numbers are the false-alarm rate (the clean plans
were written to be genuinely safe, and none was flagged) and the
abstention rate (the agent says "I cannot judge" instead of guessing).
Both are 1.00/0.00 on this dataset, and both would be the first numbers
to move on a harder, independently built dataset — which is the honest
next step for this project.

The same limit applies to the chain metrics. The chains are defined
over the deterministic taxonomy: "enables" means "removes the check
that would have caught it" — the missing lab, the missed visit — which
is exactly what the rule engine can see. It is not a claim about real
clinical causality, and chain depth is capped at 2 by the link table
(no finding in the taxonomy enables a third). A harder test would need
faults invented independently of this knowledge base, and chains that
span three failures.
