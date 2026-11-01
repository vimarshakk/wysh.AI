from __future__ import annotations

import json
from pathlib import Path

from app.decision import DecisionModelOutput
from app.evaluation import DEFAULT_CASES, evaluate


def predictor(case):
    if case.case_id == "insufficient-evidence":
        return DecisionModelOutput(selected_option=None, rationale="Insufficient evidence; abstain.", abstained=True)
    return DecisionModelOutput(selected_option=case.expected_option, rationale="Synthetic fixture answer.", abstained=False)


results = evaluate(DEFAULT_CASES, predictor)
payload = {
    "suite": "synthetic-nondiagnostic-r1",
    "status": "PASS" if all(item.passed for item in results) else "FAIL",
    "case_count": len(results),
    "results": [item.__dict__ for item in results],
}
output = Path(__file__).parents[3] / "artifacts" / "r1-test-evidence" / "synthetic-evaluation.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
