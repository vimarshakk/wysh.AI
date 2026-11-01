# Capability Matrix

| Capability | wysh.AI now | Upstream pattern | Decision | Acceptance evidence |
|---|---|---|---|---|
| FHIR R4 Observation mapping | `apps/api/app/fhir_adapter.py` | cql-exec-fhir patient Bundle source | Adapted boundary | `test_r1.py`, `test_reuse_accelerator.py` |
| JSON ELM identity and execution boundary | `apps/api/app/standards_cql.py` | cql-execution JSON ELM library/executor split | Isolated subset | `test_standards_fhir_elm_vertical_slice_is_allowlisted_and_evidence_linked` |
| CQL feature conformance | bounded synthetic subset only | cql-tests/cql-execution | Deferred | Must use pinned upstream runtime before claiming conformance |
| Rule lifecycle | `rule_governance_store.py` | authoring/governance patterns | Original implementation | R6B governance gate |
| FHIR/CQL server | none | Blaze/CQF Ruler | Reference/isolated future | No external server connected |
| Terminology | explicit local code map | Snowstorm/HAPI terminology | Deferred | License/content review required |
| Model serving | local provider adapters | Ollama/vLLM patterns | Adapted architecture | existing local MedGemma evidence |
| Research ML | contracts only | PyHealth/OHDSI/TorchEHR | Research-only | no PHI, training, or risk claims |
| Imaging | abstaining contract | MONAI/nnU-Net/MedSAM | Research-only | imaging contract gate |
| Authorization | signed gateway tokens + role checks | OpenFGA/Keycloak patterns | Preserve current identity | R4/R6B negative tests |
