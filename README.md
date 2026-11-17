# Clinical Pre-Mortem Agent

> Before a care plan is finalised, this agent assumes it has already harmed the patient — and works backwards to name the specific failure, its earliest warning sign, and the one change that would have prevented it.

**Author:** Amna Raheeba · Transfers my Failure Imagination technique from predictive maintenance ([agentic-phm-self-healing](https://github.com/Amna-Raheeba/agentic-phm-self-healing), where an agent imagines the failure cycle of a machine) to clinical care plans — and plugs into my evaluation platform ([ai-evaluation-platform](https://github.com/Amna-Raheeba/ai-evaluation-platform)) as a new kind of agent to measure.

> **Research prototype. Synthetic plans only. Not clinical guidance, not a medical device, never to be used on a real patient.** The knowledge base is a small demo table, not a formulary.

---

## 1. Overview

### 1.1 The problem

A care plan is a list of decisions, and a bad decision only shows up
after the harm. Existing clinical decision support answers
counterfactual questions — CausalGuard asks "treatment A vs B",
ClinicalAgents searches for a diagnosis — but nothing does
**prospective hindsight on a plan**: assume the plan failed, and say
exactly how, when the first sign would have appeared, and what single
change would have stopped it.

### 1.2 The idea

A **pre-mortem agent**: six deterministic detectors over a six-category
failure taxonomy (missed allergy, renal dose error, drug interaction,
missing follow-up, contradictory instruction, unmonitored lab). Findings
are ranked by severity × plausibility. For the top two, the agent
computes the **minimal plan edit that kills the failure** — substitute
one drug, reduce one dose, hold one drug, schedule the follow-up, fix
the instruction, order the missing lab — and *verifies* the edit by
re-running the detectors: the failure must disappear and no new failure
may appear. Where the evidence is absent (no eGFR, unknown allergy
history), the agent **abstains** instead of guessing.

It also finds **second-order failure chains**: when one failure enables
a second — the missing lab is the test that would have revealed the
drug accumulating, the missed visit is where the interaction would have
been caught — and computes the **single edit that breaks the chain**,
verified by re-running chain detection on the edited plan. No
pre-mortem tool models failure chains within a plan.

The verdict is code. Language-model prose is used only to narrate the
failure story, never to decide it — and the offline version works with a
deterministic mock storyteller.

### 1.3 What it is not

- Not a diagnosis tool: it reviews a plan that is already written.
- Not a clinical system: the knowledge base is a demo table of standard,
  widely taught facts.
- Not a claim about real-world performance: the evaluation measures the
  agent against faults injected from its own knowledge base (see §5).

## 2. How It Works

### 2.1 Pipeline

```
CarePlan
  -> abstention    refuse categories whose evidence is absent
  -> detectors     six deterministic detectors, one per category
  -> ranking       severity x plausibility, highest risk first
  -> stories       failure story per finding (prose only)
  -> edits         minimal edit for the top 2, verified by re-running
  -> chains        second-order chains + the one edit that breaks each
  -> PreMortemReport: verdict + ranked findings + stories + edits + chains
```

### 2.2 Failure chains (second-order)

A chain is two findings where the first *enables* the second: the
enabler removes the check that would have caught the enabled failure.
A chain exists only when the (enabler, enabled) category pair is in
the link table (`knowledge.CHAIN_LINKS`) **and** the two findings
share a drug:

| Enabler | Enabled | The link |
|---|---|---|
| unmonitored_lab | renal_dose_error | the missing lab is the test that would have revealed the drug accumulating |
| unmonitored_lab | drug_interaction | the missing lab is the test that would have revealed the interaction's harm |
| missing_follow_up | drug_interaction | the missed visit is where the interaction would have been caught |
| missing_follow_up | renal_dose_error | the missed visit is where the dose would have been reviewed |

Breaking a chain takes one edit, and it targets the enabler: order
the missing lab, or schedule the missed visit. The break is verified
by re-running chain detection on the edited plan — the chain is
broken only when the edit is valid and no chain remains. Breaking the
chain restores detection; it does **not** fix the enabled failure
itself, which still needs its own edit. "Enables" is a statement
about this deterministic taxonomy, not a claim about real clinical
causality — the chains are defined over the rule engine's own checks.

### 2.3 Failure taxonomy

| Category | Severity | Example |
|---|---|---|
| missed_allergy | 5 | amoxicillin prescribed despite a penicillin allergy |
| renal_dose_error | 4 | metformin 2000 mg/day at eGFR 25 (contraindicated) |
| drug_interaction | 4 | warfarin + ibuprofen (major-bleed risk) |
| missing_follow_up | 3 | new warfarin, no follow-up scheduled |
| contradictory_instruction | 2 | same drug at two different doses |
| unmonitored_lab | 3 | warfarin with no INR ordered |

### 2.4 Minimal edits

| Failure | Edit |
|---|---|
| missed_allergy | substitute the drug (or stop it if no substitute exists) |
| renal_dose_error | reduce to the eGFR limit (or stop if contraindicated) |
| drug_interaction | hold the newly started drug |
| missing_follow_up | schedule follow-up within the required window |
| contradictory_instruction | keep one consistent dose and instruction |
| unmonitored_lab | order the missing labs |

Every edit is verified: applied to a copy of the plan, detectors
re-run. An edit that trades one failure for another is reported
**invalid**, not hidden.

## 3. Quickstart

```bash
git clone https://github.com/Amna-Raheeba/clinical-pre-mortem-agent.git
cd clinical-pre-mortem-agent
python -m clinical_pre_mortem_agent demo        # demo plan, printed report
python -m clinical_pre_mortem_agent evaluate    # seeded evaluation, 42 cases
python -m clinical_pre_mortem_agent check --plan examples/sample_plan.json
```

No dependencies for the core package — standard library only, CPU-only,
fully offline. Dashboard only:

```bash
pip install streamlit
streamlit run dashboard/app.py
```

## 4. Usage

```python
from clinical_pre_mortem_agent import run_pre_mortem, sample_plan

report = run_pre_mortem(sample_plan())
print(report.verdict)                    # RISKS FOUND
for finding in report.ranked_findings:
    print(finding.category, finding.risk_score, finding.detail)
for edit in report.edits:
    print(edit.action, "valid:", edit.is_valid)
```

Plans are plain JSON — see `examples/sample_plan.json` and
`clinical_pre_mortem_agent/plan_io.py`. A missing `egfr` stays missing
(it triggers an abstention); nothing is silently guessed.

## 5. Measured Results

Seeded synthetic dataset: 50 cases (24 faulty, 4 per category; 8
chained, 2 per link; 12 clean; 6 evidence-absent). All measured on
2026-11-17, reproducible with
`python -m clinical_pre_mortem_agent evaluate`:

| Metric | Value |
|---|---|
| Failure recall | **1.00** (40/40 injected faults found) |
| False-alarm rate | **0.00** (0/12 clean plans flagged) |
| Minimal-edit success | **1.00** (40/40 edits verified valid) |
| Abstention rate | **1.00** (6/6 correct abstentions) |
| Chain recall | **1.00** (8/8 expected chains found) |
| Chain-break rate | **1.00** (8/8 chains broken by one verified edit) |
| False-chain rate | **0.00** (0/12 clean plans with a chain) |

Per-category recall is 4/4 in every category — 8/8 for the four
categories the chains touch (`notebooks/02_evaluation_experiment.py`).
The demo plan itself carries one chain: unmonitored_lab ->
drug_interaction (warfarin, no INR), broken by ordering the INR.

**Honest limit:** the faults are injected from the same knowledge base
the detectors read, so recall measures consistency, not performance on
faults invented by someone else or on real prescribing data. The
false-alarm rate and the abstention rate are the numbers that would move
first on an independently built dataset — which is the honest next step
for this project. The same limit applies to the chains: they are
defined over the deterministic taxonomy, not real clinical causality —
"enables" means "removes the check that would have caught it", which
is exactly what the rule engine can see. Full discussion in
`docs/metrics.md`.

## 6. Repository Layout

```
clinical_pre_mortem_agent/   core package (stdlib only)
  models.py  knowledge.py  taxonomy.py  detectors.py
  abstention.py  ranking.py  stories.py  edits.py  chains.py
  pre_mortem.py  evaluation.py  plan_io.py  __main__.py
tests/                       89 tests, plain pytest (incl. Streamlit AppTest)
dashboard/                   Streamlit app + helpers (runs the real pipeline)
data/eval_plans.json         the full seeded evaluation dataset (50 cases)
docs/                        architecture.md, metrics.md, experiment_log.md
examples/                    sample_plan.json, sample_report.md
notebooks/                   01 demo run, 02 evaluation experiment
results/                     evaluation.json, evaluation.csv
```

## 7. Tests

```bash
pip install pytest
pytest -q        # 89 passed
```

CI runs plain `pytest` on Python 3.10/3.11/3.12, plus the demo, the
evaluation, and the evaluation notebook. The dashboard AppTest is part
of the suite (Streamlit is installed in CI for it).
