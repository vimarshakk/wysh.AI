# WDI-20 open-source acceleration

The disease-management research was translated into original Wysh.AI boundaries rather than copied applications.

| Pattern learned | Wysh.AI implementation |
|---|---|
| Nightscout CGM ingestion and time-series monitoring | Synthetic `LongitudinalMeasurement` contract and descriptive trend engine. Automated insulin dosing is intentionally excluded. |
| Bahmni/OpenMRS longitudinal workflow | Shared WDI disease catalog, patient/clinician/pharmacy/research experience contract, and review boundary. |
| AHRQ CQL Services REST/CDS Hooks shape | Original deterministic rule endpoint with versioned rule manifest; future CQL adapter can sit behind it. |
| OpenEMR FHIR/EHR interoperability | Synthetic FHIR R4 Observation adapter with an explicit code map and unknown-code abstention. |

The first implemented clinical-rule packs cover diabetes, hypertension, and chronic kidney disease completeness checks. They identify missing typed measurements and preserve evidence references; they do not calculate risk, diagnose disease, recommend treatment, or trigger alerts autonomously.

The audited source projects remain outside the source tree. Their source code, UI assets, datasets, and licenses are not silently combined with Wysh.AI.
