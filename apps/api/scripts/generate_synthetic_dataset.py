"""Generate synthetic disease-specific intelligence dataset for validation.

Creates de-identified synthetic JSONL datasets matching the clinical-telemetry-v1
schema, with disease-specific measurements for diabetes, hypertension, CKD,
and other conditions. All data is synthetic; no PHI or real patient records
are included.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).parents[2]
OUTPUT_DIR = ROOT / "research" / "datasets"

RANDOM_SEED = 20261102
random.seed(RANDOM_SEED)

DISEASE_CONFIGS = {
    "diabetes": {
        "hba1c_percent": (6.0, 2.0),  # mean, std
        "mean_glucose_mg_dl": (140.0, 40.0),
        "age_years": (55.0, 15.0),
    },
    "hypertension": {
        "bp_systolic_mmhg": (135.0, 25.0),
        "bp_diastolic_mmhg": (85.0, 15.0),
        "age_years": (60.0, 15.0),
    },
    "chronic_kidney_disease": {
        "egfr_ml_min_1_73m2": (75.0, 25.0),
        "urine_albumin_mg_g": (25.0, 40.0),
        "age_years": (65.0, 15.0),
    },
    "hyperlipidemia": {
        "total_cholesterol_mg_dl": (200.0, 40.0),
        "ldl_mg_dl": (120.0, 35.0),
        "hdl_mg_dl": (55.0, 15.0),
        "triglycerides_mg_dl": (150.0, 80.0),
        "age_years": (55.0, 15.0),
    },
    "hypothyroidism": {
        "tsh_mIU_L": (3.5, 10.0),
        "free_t4_ng_dL": (1.0, 0.5),
        "age_years": (50.0, 15.0),
    },
    "asthma": {
        "fev1_L": (3.0, 0.8),
        "fev1_fvc_ratio": (0.75, 0.1),
        "peak_flow_L_min": (400.0, 100.0),
        "age_years": (35.0, 20.0),
    },
    "depression": {
        "phq9_score": (8.0, 5.0),
        "symptom_duration_weeks": (8.0, 8.0),
        "age_years": (35.0, 15.0),
    },
    "osteoarthritis": {
        "pain_score_0_10": (4.0, 2.0),
        "mobility_score_0_10": (5.0, 2.0),
        "age_years": (65.0, 15.0),
    },
}


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _generate_disease_row(patient_idx: int, disease_id: str) -> dict:
    patient_id = f"synthetic-{disease_id}-p{patient_idx:04d}"
    observed_at = "2026-01-01T00:00:00Z"
    config = DISEASE_CONFIGS[disease_id]

    row = {
        "patient_id": patient_id,
        "observed_at": observed_at,
        "disease_id": disease_id,
    }

    for metric, (mean, std) in config.items():
        value = random.normalvariate(mean, std)
        # Clip to reasonable clinical ranges
        if metric == "age_years":
            value = max(18, min(95, value))
        elif metric in ("egfr_ml_min_1_73m2",):
            value = max(10, min(150, value))
        elif metric in ("bp_systolic_mmhg", "bp_diastolic_mmhg"):
            value = max(60, min(220, value))
        elif metric in ("urine_albumin_mg_g",):
            value = max(5, min(500, value))
        row[metric] = round(value, 2)

    # Add label based on simple clinical thresholds
    row["synthetic_review_required"] = _determine_label(disease_id, row)
    return row


def _determine_label(disease_id: str, row: dict) -> int:
    """Determine synthetic review label based on simple clinical thresholds."""
    if disease_id == "diabetes":
        hba1c = row.get("hba1c_percent", 0)
        glucose = row.get("mean_glucose_mg_dl", 0)
        return 1 if hba1c >= 6.5 or glucose >= 126 else 0
    elif disease_id == "hypertension":
        sbp = row.get("bp_systolic_mmhg", 0)
        dbp = row.get("bp_diastolic_mmhg", 0)
        return 1 if sbp >= 130 or dbp >= 80 else 0
    elif disease_id == "chronic_kidney_disease":
        egfr = row.get("egfr_ml_min_1_73m2", 100)
        uacr = row.get("urine_albumin_mg_g", 0)
        return 1 if egfr <= 60 or uacr >= 30 else 0
    elif disease_id == "hyperlipidemia":
        total = row.get("total_cholesterol_mg_dl", 0)
        ldl = row.get("ldl_mg_dl", 0)
        return 1 if total >= 200 or ldl >= 130 else 0
    elif disease_id == "hypothyroidism":
        tsh = row.get("tsh_mIU_L", 0)
        return 1 if tsh > 4.5 else 0
    elif disease_id == "asthma":
        fev1 = row.get("fev1_L", 3.0)
        return 1 if fev1 < 2.5 else 0
    elif disease_id == "depression":
        phq9 = row.get("phq9_score", 0)
        return 1 if phq9 >= 10 else 0
    elif disease_id == "osteoarthritis":
        pain = row.get("pain_score_0_10", 0)
        return 1 if pain >= 5 else 0
    elif disease_id == "pcos":
        hba1c = row.get("hba1c_percent", 0)
        return 1 if hba1c >= 6.0 else 0
    elif disease_id == "tuberculosis":
        adherence = row.get("treatment_adherence", 100)
        return 1 if adherence < 80 else 0
    else:
        return 0


def generate_dataset(num_patients_per_disease: int = 50) -> list[dict]:
    """Generate synthetic dataset for all diseases."""
    rows = []
    patient_counter = 0

    for disease_id in DISEASE_CONFIGS:
        for i in range(num_patients_per_disease):
            patient_counter += 1
            row = _generate_row(patient_counter, disease_id)
            rows.append(row)

    return rows


def main() -> None:
    output_path = OUTPUT_DIR / "r8-synthetic-validation-v1.jsonl"
    rows = generate_dataset(n_rows := 50)

    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")

    review_count = sum(1 for r in rows if r["synthetic_review_required"] == 1)
    print(f"Generated {len(rows)} synthetic rows to {output_path}")
    print(f"Review-required (label=1): {review_count} ({review_count / len(rows) * 100:.1f}%)")
    print(f"Diseases: {list(DISEASE_CONFIGS.keys())}")


if __name__ == "__main__":
    main()
