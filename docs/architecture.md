# Architecture

## 1. Idea

A pre-mortem is prospective hindsight: before a care plan is finalised,
assume it has already harmed the patient, then work backwards to the
specific failure, its earliest warning sign, and the one change that
would have prevented it. This transfers the Failure Imagination
technique from my PHM project (`agentic-phm-self-healing`, where an
agent rolls sensor trajectories forward to imagine the failure cycle) to
clinical care plans — but with a rule engine instead of a simulator,
because a care plan is a list of decisions, not a time series.

Closest prior work: CausalGuard (counterfactual-aware clinical decision
support, asks "treatment A vs B") and ClinicalAgents (MCTS diagnosis
search). Neither does prospective-hindsight failure analysis on a plan.
That gap is the invention.

## 2. Pipeline

```
CarePlan (JSON / Python objects)
  -> abstention.py      refuse categories whose evidence is absent
  -> detectors.py       six deterministic detectors, one per category
  -> ranking.py         severity x plausibility, highest risk first
  -> stories.py         failure story per finding (prose only)
  -> edits.py           minimal edit for the top 2, verified by re-running
  -> chains.py          second-order chains + the one edit that breaks each
  -> PreMortemReport    verdict + ranked findings + stories + edits + chains
```

## 3. Modules

| Module | Responsibility |
|---|---|
| `models.py` | `CarePlan`, `PatientRecord`, `Medication`, `Finding`, `PlanEdit`, `Abstention`, `PreMortemReport` |
| `knowledge.py` | Demo knowledge base: allergy classes, renal dose limits, interactions, monitoring, follow-up, administration, alternatives |
| `taxonomy.py` | The six failure categories and their fixed severities |
| `detectors.py` | Six deterministic detectors; same plan always gives the same findings |
| `abstention.py` | Refuses to judge a category when its evidence is absent |
| `ranking.py` | `risk_score = severity x plausibility`, deterministic tie-breaks |
| `stories.py` | `MockStoryteller` (deterministic templates) and `LLMStoryteller` (opt-in, raises without a backend) |
| `edits.py` | Minimal edit per failure, verified: re-run detectors, must kill the failure and add none |
| `chains.py` | Second-order chains (enabler -> enabled, shared drug) and the single verified chain-breaking edit |
| `pre_mortem.py` | Orchestrator: abstain -> detect -> rank -> imagine -> edit -> chain |
| `evaluation.py` | Seeded synthetic dataset (50 cases) and the seven metrics |
| `plan_io.py` | Plan JSON load/save, shared by CLI and dashboard |

## 4. Design rules

1. **The verdict is code.** A finding exists only when a detector's rule
   matches the plan. Prose never creates, removes, or changes a finding.
2. **Edits never mutate.** `CarePlan.copy_with` builds a new plan; the
   edit is verified on the copy.
3. **Missing evidence abstains.** A missing eGFR is not treated as a
   healthy kidney; it is reported as "cannot judge".
4. **One fault, one finding.** Detectors are written so a single fault
   fires once (e.g. an instruction that both contradicts its pair and
   the drug standard is reported once).
5. **Stdlib only, offline.** No model, no network, no GPU. The optional
   LLM storyteller is opt-in and raises without a backend.
6. **Synthetic data only.** Every patient is hand-built and labelled
   synthetic. No real patient data, ever.

## 5. What it is not

- Not a clinical decision support system and not a medical device. The
  knowledge base is a small demo table, not a formulary. Nothing here
  should be used on a real patient.
- Not a diagnosis tool. It reviews a *plan* that is already written; it
  does not propose treatments.
- Not a benchmark of real-world performance. The evaluation measures the
  agent against faults injected from its own knowledge base (see
  `docs/experiment_log.md` for the honest limit).
