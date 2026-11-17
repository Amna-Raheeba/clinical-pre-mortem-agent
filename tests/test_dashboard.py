"""Streamlit AppTest for dashboard/app.py.

Skipped when Streamlit is not installed (the bare test venv has no
Streamlit; CI installs it). The default sample plan is the demo plan,
which carries one failure chain, so the pre-mortem run must show the
chains section as well as the verdict and the findings table.
"""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")


def _markdown_text(at: AppTest) -> str:
    # Verdicts render as success/error/warning alerts, subheaders and
    # metrics are their own element types — gather them all as text.
    parts = [str(m.value) for m in at.markdown]
    parts += [str(s.value) for s in at.subheader]
    for alerts in (at.success, at.error, at.warning, at.info):
        parts += [str(a.value) for a in alerts]
    for metric in at.metric:
        parts.append(f"{metric.label} {metric.value}")
    return "\n".join(parts)


def test_dashboard_loads_with_no_exceptions():
    at = AppTest.from_file(APP)
    at.run()
    assert not at.exception


def test_dashboard_pre_mortem_run_shows_verdict_and_chain():
    at = AppTest.from_file(APP)
    at.run()
    assert not at.exception
    at.button[0].click().run(timeout=30)
    assert not at.exception
    text = _markdown_text(at)
    assert "RISKS FOUND" in text
    assert "Failure chains" in text
    assert "unmonitored_lab" in text
    assert "drug_interaction" in text
    assert "order monitoring labs: INR" in text
    assert len(at.dataframe) >= 2  # findings table + chains table


def test_dashboard_evaluation_run_shows_all_seven_metrics():
    at = AppTest.from_file(APP)
    at.run()
    assert not at.exception
    at.button[1].click().run(timeout=30)
    assert not at.exception
    text = _markdown_text(at)
    for label in ("Failure recall", "False-alarm rate",
                  "Minimal-edit success", "Abstention rate",
                  "Chain recall", "Chain-break rate", "False-chain rate"):
        assert label in text
