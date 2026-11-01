# Open-source medical AI adoption matrix

This is an engineering adoption decision, not a clinical validation or legal license opinion. Dependencies are not copied into wysh.AI; they are treated as isolated upstream references behind the imaging contract. The machine-readable source of truth is `packages/contracts/open-source-adoption-v1.json`.

| Candidate | Decision | Why | Next gate |
|---|---|---|---|
| MONAI | Adopt as imaging foundation candidate | Mature healthcare-imaging toolkit; repository exposes an Apache-2.0 license and imaging-focused modules. | Pin version, SBOM, modality benchmark, model-weight license review. |
| OHIF-AI | Adopt as workstation/integration reference | Apache-2.0 repository with DICOM viewer, interactive segmentation, report-generation and VLM integration patterns. | Separate frontend deployment, DICOM security review, synthetic viewer E2E. |
| RadVision AI | Reference only | Repository explicitly labels itself research/educational-only and not for diagnosis or patient care. | Independent security/license audit before any code reuse. |
| MedRAX | Evaluate, do not adopt yet | Promising tool-routing architecture for chest X-ray workflows, but source/license/dependency audit is incomplete in this workspace. | Read repository license, pin commit, inspect tools/models, build synthetic adapter test. |
| MedSAM2 / nnU-Net / BiomedCLIP / LLaVA-Med | Candidate pool | Useful modality-specific capabilities, but each requires independent weight-license, benchmark, and operational review. | Add only behind a versioned model manifest and modality-specific evaluation. |

The first Wysh.AI implementation is the metadata-only `/v1/imaging/analyze`
contract. It validates study metadata and returns an explicit abstention until a
modality-specific model is enabled and evaluated.
