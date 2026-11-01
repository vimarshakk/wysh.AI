# R13 controlled open-source adoption decisions

No new upstream dependency was installed or marked `INTEGRATED` in R13.

| Candidate | Decision | Source-backed wysh.AI state | R13 acceptance gate |
| --- | --- | --- | --- |
| HAPI FHIR | REFERENCE | Synthetic R4 conformance contract only; no HAPI server | Conformance corpus, dependency/license/security review |
| CQF Clinical Reasoning | REFERENCE | Existing pinned CQL runtimes remain canonical | Differential FHIR operation and provenance tests |
| Snowstorm | DEFER | Local version-pinned terminology contract; no service | Distribution rights, terminology versioning, resource review |
| OpenFGA | ADAPT | Synthetic parity harness; signed gateway policy remains canonical | Relationship tuple parity, revocation, break-glass review |
| Microsoft Presidio | ADAPT | Synthetic-only/de-identification boundary; no dependency | Synthetic detector benchmark and false-negative review |
| MLflow | DEFER | Local JSON experiment manifests and lifecycle registry | Provenance/SBOM benefit must justify service dependency |
| PyHealth | REFERENCE | Native CPU baselines; no external code or data | License, dependency, dataset and reproducibility audit |
| OHDSI PatientLevelPrediction | REFERENCE | Evaluation methodology adapted natively | Adequate governed data and external validation |
| DVC | DEFER | SHA-256 registry and local artifact manifests | Need for remote artifact workflow plus security review |
| MONAI | ADAPT | MONAI-compatible abstaining adapter and resource contract | Approved weights, modality benchmark, resource/safety gate |
| OHIF Viewer | DEFER | Clinical Console has metadata-only imaging status | Synthetic DICOM viewer E2E and deployment review |
| Orthanc | DEFER | No image archive or raw image ingress | Isolated synthetic DICOM service and access control |
| Ollama | INTEGRATED | Real local MedGemma runtime executed and verified | Ongoing model/version and runtime safety evidence |
| vLLM | DEFER | No throughput/hardware need established | Load benchmark, isolation, cost and operations review |

`ADAPT` means native bounded implementation of a pattern, not upstream integration. `INTEGRATED` is reserved for code/runtime genuinely executed in wysh.AI.
