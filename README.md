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
  -> PreMortemReport: verdict + ranked findings + stories + edits
```

### 2.2 Failure taxonomy

| Category | Severity | Example |
|---|---|---|
| missed_allergy | 5 | amoxicillin prescribed despite a penicillin allergy |
| renal_dose_error | 4 | metformin 2000 mg/day at eGFR 25 (contraindicated) |
| drug_interaction | 4 | warfarin + ibuprofen (major-bleed risk) |
| missing_follow_up | 3 | new warfarin, no follow-up scheduled |
| contradictory_instruction | 2 | same drug at two different doses |
| unmonitored_lab | 3 | warfarin with no INR ordered |

### 2.3 Minimal edits

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

Seeded synthetic dataset: 42 cases (24 faulty, 4 per category; 12
clean; 6 evidence-absent). All measured on 2026-11-17, reproducible with
`python -m clinical_pre_mortem_agent evaluate`:

| Metric | Value |
|---|---|
| Failure recall | **1.00** (24/24 injected faults found) |
| False-alarm rate | **0.00** (0/12 clean plans flagged) |
| Minimal-edit success | **1.00** (24/24 edits verified valid) |
| Abstention rate | **1.00** (6/6 correct abstentions) |

Per-category recall is 4/4 in every category (`notebooks/02_evaluation_experiment.py`).

**Honest limit:** the faults are injected from the same knowledge base
the detectors read, so recall measures consistency, not performance on
faults invented by someone else or on real prescribing data. The
false-alarm rate and the abstention rate are the numbers that would move
first on an independently built dataset — which is the honest next step
for this project. Full discussion in `docs/metrics.md`.

## 6. Repository Layout

```
clinical_pre_mortem_agent/   core package (stdlib only)
  models.py  knowledge.py  taxonomy.py  detectors.py
  abstention.py  ranking.py  stories.py  edits.py
  pre_mortem.py  evaluation.py  plan_io.py  __main__.py
tests/                       72 tests, plain pytest
dashboard/                   Streamlit app + helpers (runs the real pipeline)
data/eval_plans.json         the full seeded evaluation dataset
docs/                        architecture.md, metrics.md, experiment_log.md
examples/                    sample_plan.json, sample_report.md
notebooks/                   01 demo run, 02 evaluation experiment
results/                     evaluation.json, evaluation.csv
```

## 7. Tests

```bash
pip install pytest
pytest -q        # 72 passed
```

CI runs plain `pytest` on Python 3.10/3.11/3.12, plus the demo, the
evaluation, and the evaluation notebook.
