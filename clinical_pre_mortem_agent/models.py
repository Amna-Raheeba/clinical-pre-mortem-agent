"""Data models for the clinical pre-mortem agent.

Everything here is plain data about a *synthetic* care plan. No real
patient data is ever used: plans are hand-built or generated from the
seeded synthetic generator in :mod:`evaluation`.

A :class:`CarePlan` is the unit the agent reviews: one synthetic patient,
their recorded history, the medications proposed, the follow-up schedule,
the monitoring labs ordered, and the written instructions. Every field the
rule engine needs is explicit, so a missing value is visible as a missing
value (and can trigger an abstention) instead of being silently guessed.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Medication:
    """One medication in a proposed care plan."""

    name: str  # generic name, lowercase, e.g. "amoxicillin"
    dose_mg: float  # single dose, in milligrams
    doses_per_day: int = 1
    is_new: bool = False  # started with this plan (vs continued)
    route: str = "oral"

    @property
    def daily_dose_mg(self) -> float:
        return self.dose_mg * self.doses_per_day


@dataclass(frozen=True)
class LabResult:
    """One recorded laboratory result (or one ordered monitoring lab)."""

    name: str  # e.g. "potassium", "INR", "creatinine"
    value: float | None = None  # None means ordered but not yet resulted
    unit: str = ""
    days_ago: int = 0  # how old the result is; 0 = ordered now


@dataclass(frozen=True)
class PatientRecord:
    """The synthetic patient's recorded history."""

    patient_id: str
    display_name: str  # e.g. "Mrs A (synthetic)"
    age_years: int
    sex: str = "F"
    weight_kg: float | None = None
    egfr: float | None = None  # mL/min/1.73m^2; None = not recorded
    allergies: tuple[str, ...] = ()  # drug names or classes, lowercase
    allergies_known: bool = True  # False = allergy history not recorded
    conditions: tuple[str, ...] = ()  # e.g. "chronic kidney disease"
    labs: tuple[LabResult, ...] = ()


@dataclass
class CarePlan:
    """A proposed care plan under pre-mortem review."""

    plan_id: str
    patient: PatientRecord
    medications: list[Medication] = field(default_factory=list)
    follow_up_days: int | None = None  # None = no follow-up scheduled
    monitoring_labs: tuple[str, ...] = ()  # lab names ordered for monitoring
    instructions: tuple[str, ...] = ()  # written instructions, verbatim
    indication: str = ""  # what the plan is treating, e.g. "chest infection"

    def copy_with(self, **changes) -> "CarePlan":
        """A shallow copy with the given fields replaced (edits never mutate)."""
        kwargs = {
            "plan_id": self.plan_id,
            "patient": self.patient,
            "medications": list(self.medications),
            "follow_up_days": self.follow_up_days,
            "monitoring_labs": self.monitoring_labs,
            "instructions": self.instructions,
            "indication": self.indication,
        }
        kwargs.update(changes)
        return CarePlan(**kwargs)


@dataclass(frozen=True)
class Finding:
    """One failure the rule engine found in a plan.

    The verdict is code, not prose: a finding is a category, the drug(s)
    involved, the evidence (named record fields), a severity (1-5) and a
    plausibility (0-1). The story is generated separately and never changes
    the verdict.
    """

    category: str  # one of the six taxonomy categories
    drug: str  # primary drug involved ("" when none, e.g. follow-up)
    detail: str  # one-line statement of what is wrong
    evidence: tuple[str, ...]  # named facts, e.g. "allergy: penicillin"
    severity: int  # 1 (low) to 5 (life-threatening)
    plausibility: float  # 0-1, how strongly the record supports this failure
    earliest_warning_sign: str = ""  # first observable sign, if it happens

    @property
    def risk_score(self) -> float:
        """severity x plausibility — the ranking key."""
        return self.severity * self.plausibility


@dataclass(frozen=True)
class PlanEdit:
    """A minimal edit proposed to kill one failure."""

    target_category: str
    drug: str
    action: str  # e.g. "substitute amoxicillin -> azithromycin"
    description: str
    kills_failure: bool  # verified: detector no longer fires after the edit
    introduces_new_failure: bool  # verified: no new finding appears

    @property
    def is_valid(self) -> bool:
        return self.kills_failure and not self.introduces_new_failure


@dataclass(frozen=True)
class Abstention:
    """A category the agent refuses to judge because evidence is absent."""

    category: str
    reason: str  # which evidence is missing, e.g. "eGFR not recorded"


@dataclass
class PreMortemReport:
    """The full output of one pre-mortem review."""

    plan_id: str
    findings: list[Finding]
    ranked_findings: list[Finding]  # findings sorted by risk_score, desc
    stories: dict[str, str]  # category -> failure story (prose only)
    edits: list[PlanEdit]  # minimal edits for the top failures
    abstentions: list[Abstention]
    verdict: str  # "SAFE" | "RISKS FOUND" | "ABSTAINED" | "RISKS FOUND + ABSTAINED"

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "verdict": self.verdict,
            "findings": [
                {
                    "category": f.category,
                    "drug": f.drug,
                    "detail": f.detail,
                    "evidence": list(f.evidence),
                    "severity": f.severity,
                    "plausibility": f.plausibility,
                    "risk_score": round(f.risk_score, 2),
                    "earliest_warning_sign": f.earliest_warning_sign,
                }
                for f in self.ranked_findings
            ],
            "edits": [
                {
                    "target_category": e.target_category,
                    "drug": e.drug,
                    "action": e.action,
                    "description": e.description,
                    "kills_failure": e.kills_failure,
                    "introduces_new_failure": e.introduces_new_failure,
                    "is_valid": e.is_valid,
                }
                for e in self.edits
            ],
            "abstentions": [
                {"category": a.category, "reason": a.reason} for a in self.abstentions
            ],
            "stories": self.stories,
        }
