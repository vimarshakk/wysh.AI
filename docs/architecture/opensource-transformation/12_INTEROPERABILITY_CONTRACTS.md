# Interoperability Contracts

Current contract path:

`synthetic FHIR R4 Bundle → Observation code allowlist → LongitudinalMeasurement → JSON ELM subset → evidence refs/hash`

Supported local codes are defined in `apps/api/app/fhir_adapter.py`. Unknown codes are ignored rather than guessed. The standards adapter requires a synthetic Bundle tag, FHIR version `4.0.1` metadata, exact library identity, an allowlisted expression, and an `Exists`/`Retrieve` shape targeting `FHIR.Observation`.

This is not a general FHIR server, CQL compiler, terminology service, CDS Hooks endpoint, or ABDM integration. Those remain separate future contracts.

R7B adds a versioned synthetic terminology contract in `apps/api/app/terminology.py`. It validates only two synthetic LOINC identifiers and one synthetic ValueSet URL; it does not provide SNOMED CT or licensed terminology content.
