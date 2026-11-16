# Changelog

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
