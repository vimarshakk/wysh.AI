# R15 clinical validation protocols

These are protocol templates, not an approved clinical study.

## Disease workflow protocol

For each disease pack, define the index date, eligible population, observation
window, prediction/monitoring horizon, feature cutoff, outcome definition,
reference standard, abstention policy, primary endpoint, secondary endpoints,
missing-data handling, subgroup plan, calibration plan, and sample-size
methodology before inspecting outcome labels.

Required safeguards include patient-level and temporal separation, leakage
review, locked model/rule versions, blinded or independently adjudicated
reference standards, prespecified analysis, confidence intervals, and explicit
`INSUFFICIENT_SAMPLE`/`OUT_OF_DISTRIBUTION` outcomes.

## MedGemma safety protocol

Evaluate schema validity, evidence grounding, fabricated references, unsafe
diagnostic or treatment language, prompt injection, contradiction handling,
missing evidence, provenance mismatch, abstention, and model unavailability.
The primary safety analysis must be performed by independent qualified
reviewers using a prespecified rubric; JSON validity alone is not a pass.

## No-study boundary

No real patient data, prospective recruitment, clinical intervention,
diagnostic claim, or clinical decision may begin under R15 engineering
authorization.
