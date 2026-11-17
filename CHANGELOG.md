# Changelog

## 0.2.0 — 2026-11-17

- **Second-order failure chains (new):** when one failure enables a
  second — the missing lab is the test that would have revealed the
  drug accumulating, the missed visit is where the interaction would
  have been caught — the agent reports the chain (depth, enabling
  link, chain risk) and the single edit that breaks it, verified by
  re-running chain detection on the edited plan. Measured on 8 seeded
  chained cases: chain recall 1.00 (8/8), chain-break rate 1.00 (8/8),
  false-chain rate 0.00 (0/12 clean plans). Dataset now 50 cases.
- Knowledge base: gentamicin follow-up within 3 days (levels must be
  reviewed shortly after starting).
- Dashboard: failure-chains section in the pre-mortem tab and the
  three chain metrics in the evaluation tab.
- Audit fixes: `data/eval_plans.json` is now loaded by
  `load_eval_cases()` and pinned to the code-built dataset by test;
  removed unused `SEED` and the empty `scripts/` directory; fixed the
  `requirements-dev.txt` reference in `requirements.txt`; the
  Streamlit AppTest is now a real test (`tests/test_dashboard.py`)
  and CI installs Streamlit for it. 89 tests.

## 0.1.0 — 2026-11-17

Initial release.

- Prospective-hindsight pre-mortem for synthetic care plans: assume the
  plan already harmed the patient, name the failure, its earliest
  warning sign, and the one change that would have prevented it.
- Six-category deterministic taxonomy (missed allergy, renal dose error,
  drug interaction, missing follow-up, contradictory instruction,
  unmonitored lab) with severity x plausibility ranking.
- Minimal plan edits for the top two failures, verified by re-running
  the detectors (must kill the failure, must add none).
- Abstention when evidence is absent (no eGFR, unknown allergy history,
  missing weight for weight-based dosing).
- Deterministic mock storyteller; optional LLM storyteller that raises
  without a backend instead of fabricating prose.
- Seeded evaluation: 42 synthetic cases — failure recall 1.00 (24/24),
  false-alarm rate 0.00 (0/12), minimal-edit success 1.00 (24/24),
  abstention rate 1.00 (6/6).
- Streamlit dashboard running the real pipeline; CLI (`demo`, `check`,
  `evaluate`); 72 tests, CI on Python 3.10/3.11/3.12.
