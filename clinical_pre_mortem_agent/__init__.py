"""Clinical Pre-Mortem Agent — prospective-hindsight failure analysis for care plans.

Before a care plan is finalised, this agent assumes it has already
harmed the patient and works backwards: it names the specific failure,
its earliest warning sign, and the one change that would have prevented
it. The verdict is deterministic rule code over a six-category taxonomy;
language-model prose is used only to narrate the failure story, never to
decide it. All data is synthetic — never real patient data.

Public API: :func:`run_pre_mortem`, :class:`CarePlan`,
:class:`PatientRecord`, :class:`Medication`, :func:`evaluate`,
:func:`detect_chains`, :func:`break_chain`.
"""

__version__ = "0.2.0"

from .chains import break_chain, detect_chains
from .evaluation import build_eval_dataset, evaluate, load_eval_cases, sample_plan
from .models import (
    CarePlan,
    ChainBreak,
    FailureChain,
    LabResult,
    Medication,
    PatientRecord,
)
from .pre_mortem import run_pre_mortem

__all__ = [
    "__version__",
    "run_pre_mortem",
    "CarePlan",
    "PatientRecord",
    "Medication",
    "LabResult",
    "evaluate",
    "build_eval_dataset",
    "load_eval_cases",
    "sample_plan",
    "detect_chains",
    "break_chain",
    "FailureChain",
    "ChainBreak",
]
