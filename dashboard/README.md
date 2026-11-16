# Dashboard

A Streamlit dashboard that runs the real pre-mortem pipeline live —
nothing is hardcoded or screenshotted.

## Run it

```
pip install streamlit
streamlit run dashboard/app.py
```

## Tabs

1. **Run a pre-mortem** — pick a sample plan (faulty, clean, or
   evidence-absent), run the pipeline, and see the verdict, the ranked
   failures with their stories, the verified minimal edits, and any
   abstentions.
2. **Evaluation** — run the seeded 42-case evaluation live and see the
   four metrics, plus the last saved run from `results/evaluation.json`.

## Structure

- `app.py` — the Streamlit UI only.
- `helpers.py` — the pipeline calls and the display summaries. No
  Streamlit import here, so the helpers are tested in the bare test
  suite (`tests/test_dashboard_helpers.py`).

Streamlit is a dashboard-only dependency; the core package stays
standard-library only.
