"""Generate synthetic clinical dataset for System One validation harness.

Creates a de-identified synthetic JSONL dataset matching the clinical-telemetry-v1
schema, with metrics for diabetes, hypertension, and chronic kidney disease.
All data is synthetic; no PHI or real patient records are included.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).parents[3]
OUTPUT_PATH = ROOT / "research" / "datasets" / "r8-synthetic-validation-v1.jsonl"

RANDOM_SEED = 20261101
random.seed(RANDOM_SEED)

N_ROWS = 120
INDICATIONS = ["diabetes", "hypertension", "chronic_kidney_disease"]


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _generate_row(patient_idx: int) -> dict:
    patient_id = f"synthetic-val-p{patient_idx:04d}"
    observed_at = "2026-01-01T00:00:00Z"
    indication = INDICATIONS[patient_idx % len(INDICATIONS)]

    # Base physiological values
    age = random.randint(25, 85)
    hba1c = round(random.uniform(4.0, 11.0), 1)
    glucose = round(random.uniform(80.0, 300.0), 1)
    sbp = round(random.uniform(90.0, 200.0), 1)
    dbp = round(random.uniform(50.0, 120.0), 1)
    egfr = round(random.uniform(15.0, 120.0), 1)
    uacr = round(random.uniform(5.0, 500.0), 1)

    # Label: review required if any metric is outside normal range
    # (clinical decision support: flag abnormal values for human review)
    review_required = 0
    if indication == "diabetes":
        if hba1c >= 6.5 or glucose >= 126:
            review_required = 1
    elif indication == "hypertension":
        if sbp >= 130 or dbp >= 80:
            review_required = 1
    elif indication == "chronic_kidney_disease":
        if egfr <= 60 or uacr >= 30:
            review_required = 1

    row = {
        "patient_id": patient_id,
        "observed_at": observed_at,
        # Diabetes metrics
        "hba1c_percent": hba1c,
        "mean_glucose_mg_dl": glucose,
        # Hypertension metrics
        "bp_systolic_mmhg": sbp,
        "bp_diastolic_mmhg": dbp,
        # CKD metrics
        "egfr_ml_min_1_73m2": egfr,
        "urine_acr_mg_g": uacr,
        # Demographics
        "age_years": age,
        # Label
        "synthetic_review_required": review_required,
    }
    return row


def main() -> None:
    rows = [_generate_row(i) for i in range(N_ROWS)]

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")

    review_count = sum(1 for r in rows if r["synthetic_review_required"] == 1)
    print(f"Generated {N_ROWS} synthetic rows to {OUTPUT_PATH}")
    print(f"Review-required (label=1): {review_count} ({review_count/N_ROWS*100:.1f}%)")
    print(f"Features: hba1c_percent, mean_glucose_mg_dl, bp_systolic_mmhg, bp_diastolic_mmhg, egfr_ml_min_1_73m2, urine_acr_mg_g, age_years")


if __name__ == "__main__":
    main()
