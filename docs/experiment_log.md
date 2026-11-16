# Experiment Log

## Experiment 01 — First evaluation run (2026-11-17)

**Setup:** 42 seeded synthetic cases (24 faulty, 12 clean, 6
evidence-absent), run with `python -m clinical_pre_mortem_agent evaluate`.

**Result:** failure recall 1.00 (24/24), false-alarm rate 0.00 (0/12),
minimal-edit success 1.00 (25/25 edits valid), abstention rate 1.00 (6/6).

**Bug found by the numbers:** one faulty plan (FC-3, levothyroxine with
two contradictory instructions) produced 2 findings for 1 fault — the
instruction pair contradicted *and* one instruction contradicted the
drug's standard administration. Fixed in `detectors.py`: an instruction
already part of a flagged contradictory pair is not re-flagged against
the drug standard. After the fix: 24/24 edits, one finding per fault.

**Honest limit recorded:** the faults are injected from the same
knowledge base the detectors read. Recall 1.00 therefore measures
consistency, not external validity. The false-alarm rate and the
abstention rate are the numbers that would move first on an
independently built dataset.

## Experiment 02 — Per-category recall (2026-11-17)

**Setup:** `python notebooks/02_evaluation_experiment.py` — recall per
category, false alarms by category on clean plans.

**Result:** 4/4 in every category; zero false alarms in every category.
No category is weaker than the others on this dataset, which is
expected: each detector is a direct rule for its own category. A harder
test would need faults that sit *between* categories (e.g. a renal dose
error that also changes the monitoring requirement).

## Experiment 03 — Story quality check (2026-11-17)

**Setup:** read every generated story in `examples/sample_report.md`
and the demo CLI output.

**Bugs found by reading:** (1) the unmonitored-lab story repeated
itself — "with no test scheduled to catch it, and there is no test
scheduled that would have caught it in time". Fixed by rewriting the
template to end with "The earliest sign would have been {sign}."
(2) the contradictory-instruction warning sign repeated the story's
own sentence ("missed doses, then double doses"). Fixed by changing the
sign to "a dose taken twice, then a dose missed entirely".

**Lesson:** prose bugs are only visible by reading the output, not by
running the tests — the stories are part of the deliverable and get
read, not just counted.

## Experiment 04 — Dashboard AppTest (2026-11-17)

**Setup:** Streamlit 1.67 AppTest on `dashboard/app.py` — load, click
"Run pre-mortem", click "Run evaluation".

**Result:** 0 exceptions at every step. Pre-mortem tab shows verdict
"RISKS FOUND", a 2-row findings table, and expanders for both failures.
Evaluation tab shows all four metrics (1.00 / 0.00 / 1.00 / 1.00).

**Note:** this Streamlit version's AppTest `Tab` has no `click()` —
tabs cannot be switched in the test, but both tabs' buttons are present
in the widget tree, so the evaluation button is clickable directly.
Also switched the findings table from the deprecated
`use_container_width` to `width="stretch"`.
