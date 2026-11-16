"""Plan JSON serialisation, shared by the CLI and the dashboard.

A plan is plain JSON: patient record, medications, follow-up, monitoring
labs, instructions, indication. Loading never invents a value — a
missing ``egfr`` stays ``None`` (which is exactly what triggers an
abstention), and a missing ``allergies_known`` defaults to ``True`` only
because the JSON schema says so.
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import CarePlan, LabResult, Medication, PatientRecord


def plan_to_dict(plan: CarePlan) -> dict:
    p = plan.patient
    return {
        "plan_id": plan.plan_id,
        "indication": plan.indication,
        "patient": {
            "patient_id": p.patient_id,
            "display_name": p.display_name,
            "age_years": p.age_years,
            "sex": p.sex,
            "weight_kg": p.weight_kg,
            "egfr": p.egfr,
            "allergies": list(p.allergies),
            "allergies_known": p.allergies_known,
            "conditions": list(p.conditions),
            "labs": [{"name": lab.name, "value": lab.value,
                      "unit": lab.unit, "days_ago": lab.days_ago}
                     for lab in p.labs],
        },
        "medications": [
            {"name": m.name, "dose_mg": m.dose_mg, "doses_per_day": m.doses_per_day,
             "is_new": m.is_new, "route": m.route}
            for m in plan.medications
        ],
        "follow_up_days": plan.follow_up_days,
        "monitoring_labs": list(plan.monitoring_labs),
        "instructions": list(plan.instructions),
    }


def plan_from_dict(data: dict) -> CarePlan:
    patient_data = data["patient"]
    patient = PatientRecord(
        patient_id=patient_data["patient_id"],
        display_name=patient_data["display_name"],
        age_years=patient_data["age_years"],
        sex=patient_data.get("sex", "F"),
        weight_kg=patient_data.get("weight_kg"),
        egfr=patient_data.get("egfr"),
        allergies=tuple(patient_data.get("allergies", ())),
        allergies_known=patient_data.get("allergies_known", True),
        conditions=tuple(patient_data.get("conditions", ())),
        labs=tuple(LabResult(**lab) for lab in patient_data.get("labs", ())),
    )
    return CarePlan(
        plan_id=data["plan_id"],
        patient=patient,
        medications=[Medication(**med) for med in data.get("medications", [])],
        follow_up_days=data.get("follow_up_days"),
        monitoring_labs=tuple(data.get("monitoring_labs", ())),
        instructions=tuple(data.get("instructions", ())),
        indication=data.get("indication", ""),
    )


def load_plan(path: Path) -> CarePlan:
    return plan_from_dict(json.loads(Path(path).read_text()))


def save_plan(plan: CarePlan, path: Path) -> None:
    Path(path).write_text(json.dumps(plan_to_dict(plan), indent=2) + "\n")
