# Targeted Upstream Source Audit

## CQF CQL Execution

The upstream project exposes a JavaScript/TypeScript execution library for JSON ELM. Its README separates logical execution from data-model and terminology providers and lists unsupported or evolving areas. wysh.AI now integrates pinned `3.3.2` execution in `apps/cql-runtime`, behind an allowlisted synthetic-only FastAPI bridge. Full conformance is still not claimed.

## CQL FHIR data source

The FHIR adapter pattern accepts a patient Bundle and maps FHIR resources into the execution model. wysh.AI integrates pinned `2.2.0` `cql-exec-fhir` in the same isolated lane and keeps its native typed synthetic adapter separately.

## CQF Clinical Reasoning

The project is a Java/FHIR clinical reasoning component with Gradle-managed dependencies and Apache-2.0 licensing. It is a reference for module separation and standards packaging, not a runtime dependency of the Python service.

## CQF Ruler

The project provides FHIR clinical reasoning, knowledge artifacts, and CDS Hooks patterns, while its upstream notice states functionality is migrating toward HAPI. It is reference-only for this local milestone.

## Blaze

Blaze provides a FHIR REST API, terminology operations, and CQL operations. Its server boundary is a possible isolated synthetic conformance lane, but no container or endpoint is started here.

Primary sources reviewed: [cql-execution](https://github.com/cqframework/cql-execution), [cql-exec-fhir](https://github.com/cqframework/cql-exec-fhir), [clinical-reasoning](https://github.com/cqframework/clinical-reasoning), [cqf-ruler](https://github.com/cqframework/cqf-ruler), and [Blaze](https://github.com/samply/blaze).
