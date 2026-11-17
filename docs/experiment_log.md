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

## Experiment 05 — Second-order failure chains (2026-11-17)

**Setup:** new module `chains.py` — a chain is two findings where the
first enables the second (link table `CHAIN_LINKS` in `knowledge.py`,
four links), requiring a shared drug. Breaking a chain targets the
enabler: its minimal edit, verified by re-running chain detection on
the edited plan. 8 seeded chained cases added (2 per link), dataset
now 50 cases; the demo plan itself carries one chain
(unmonitored_lab -> drug_interaction, warfarin with no INR).

**Result:** chain recall 1.00 (8/8), chain-break rate 1.00 (8/8),
false-chain rate 0.00 (0/12 clean plans). No chains anywhere else in
the dataset. The four original metrics unchanged in value on the
larger set: recall 1.00 (40/40), false-alarm rate 0.00, minimal-edit
success 1.00 (40/40), abstention rate 1.00 (6/6).

**Bugs found while building:** (1) adding gentamicin to
`FOLLOW_UP_REQUIRED` (levels must be reviewed within 3 days) made the
existing FR-4 and E-5 gentamicin cases fire a second, unintended
missing-follow-up fault — fixed by setting their follow-up to 3 days,
the same treatment the detector tests got. (2) The first draft of the
"no shared drug" test ordered no labs at all, so gentamicin fired its
own unmonitored-lab finding and chained with its own renal error —
the test was wrong, not the code; fixed by ordering the gentamicin
labs so only warfarin's unmonitored lab fires. (3) AppTest clicks
needed a 30 s timeout in a cold venv (default 3 s) — not a code
failure; the bare venv runs the same test in seconds.

**Honest limit recorded:** breaking a chain restores detection, it
does not fix the enabled failure — after ordering the INR the
interaction still fires, and the report says so. Chain depth is capped
at 2 by the link table, and "enables" means "removes the check that
would have caught it", not real clinical causality.

## Experiment 06 — Completeness audit (2026-11-17)

**Setup:** full audit of the shipped repo: plain-`pytest` suite in
the bare venv, AppTest, local-vs-remote file comparison (GitHub
connector reads of every directory), README/docs link check, TODO
scan, results regeneration check.

**Gaps found and fixed:** (1) `data/eval_plans.json` was a dead file —
nothing in the code loaded it, although the docs said the metrics were
measured on it. Fixed with `load_eval_cases()` in `evaluation.py`
plus a test pinning the JSON to the code-built dataset (50 cases,
0 mismatches), and the JSON is now regenerated from the builder.
(2) Unused `SEED = 20261117` in `evaluation.py` — removed. (3)
`requirements.txt` told the reader to `pip install -r
requirements-dev.txt`, a file that does not exist — fixed to
`pip install pytest` / `pip install streamlit`. (4) Empty `scripts/`
directory — removed. (5) The AppTest existed only as a claim in this
log, not as a test in the repo — added `tests/test_dashboard.py`
(3 tests: load, pre-mortem run with chain, evaluation run with all
seven metrics) and CI now installs Streamlit so it runs there too.

**Result after fixes:** 89 tests pass in the bare venv (plain
`pytest`, the exact CI command) and in a separate Streamlit venv;
dashboard AppTest 0 exceptions at every step; local and remote file
lists identical; `results/` regenerated from the live evaluation;
privacy scan clean.
