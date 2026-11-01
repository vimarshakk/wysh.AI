# wysh.AI R13 engineering acceptance

## Status

R13 engineering is `PASS` for the isolated synthetic scope. Clinical governance,
clinical validation, and production release remain blocked.

## Passing evidence

- Backend regression: 132 passing tests.
- R13A disease baselines: logistic and interpretable comparator pipelines reproducible for three governed synthetic cohorts.
- R13B metric correctness: pathological inputs return typed invalid/insufficient states; no favorable zero substitution.
- R13C imaging research: native non-diagnostic pixel-integrity path passes and corrupt input abstains.
- R13D real MedGemma safety: all 8 live cases returned schema-valid typed output and deterministic `PASS`/`ABSTAINED` safety states; no fixture fallback was used.
- R13E adoption decisions: documented without claiming unexecuted upstream integrations.
- R13F scorecard preservation: previous score remains 69/100.

## Engineering limitations

The expanded real MedGemma subset executed 8 synthetic cases successfully. Several
cases correctly remained `ABSTAINED` because the model output contained unsafe or
incomplete language. This is a safety result, not clinical validation. The corpus
still contains 16 cases, so the remaining 8 are not part of the live gate.

## Release boundaries

Clinical governance is `HOLD`; clinical predictive validity and imaging diagnostic validity are `NOT_ESTABLISHED`; production is `NO-GO`. No PHI, production service, large model download, protected branch, or WyshCare modification was used.
